import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
gui_path=root/"gui_local.py"
iss_path=root/"installer.iss"

# =========================================================
# CORE VERSION
# =========================================================
s=core_path.read_text(encoding="utf-8")
if "APP_VERSION = '2.2.2'" not in s and "APP_VERSION = '2.2.3'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.2.2")
s=s.replace("APP_VERSION = '2.2.2'","APP_VERSION = '2.2.3'")

# =========================================================
# WHATSAPP PHONE RESOLUTION
# WuzAPI/whatsmeow may provide both PN and LID. Prefer PN JIDs.
# =========================================================
phone_method = r'''
    def phone(self,alt='',sender='',chat=''):
        def parts(value):
            if isinstance(value,dict):
                user=str(
                    value.get('User') or value.get('user') or
                    value.get('Username') or value.get('username') or ''
                )
                server=str(
                    value.get('Server') or value.get('server') or
                    value.get('Domain') or value.get('domain') or ''
                ).lower()
                if user:
                    user=user.split(':',1)[0]
                return re.sub(r'\D+','',user),server

            raw=str(value or '').strip()
            if not raw:
                return '',''
            if '@' in raw:
                user,server=raw.split('@',1)
                user=user.split(':',1)[0]
                server=server.split('/',1)[0].lower()
                return re.sub(r'\D+','',user),server
            return re.sub(r'\D+','',raw),''

        values=(sender,alt,chat)

        # Explicit real phone-number JIDs always win over LID identifiers.
        for value in values:
            digits,server=parts(value)
            if digits and server in ('s.whatsapp.net','c.us'):
                return digits

        # Never treat a WhatsApp LID as a phone number.
        for value in values:
            digits,server=parts(value)
            if digits and server and ('lid' in server or server.endswith('hosted.lid')):
                continue
            if digits and 7<=len(digits)<=15:
                return digits

        return ''
'''
phone_method=textwrap.indent(textwrap.dedent(phone_method).strip()+"\n","    ")
s,n=re.subn(
    r"    def phone\(self,[^)]*\):.*?(?=\n    def [A-Za-z_])",
    lambda _m:phone_method.rstrip(),
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar Engine.phone")

# Do not fall back to @lid route when saving a contact.
old_resolved="            resolved_phone=normalize_contact_phone(phone or str(route).split('@',1)[0])"
new_resolved="""            resolved_phone=normalize_contact_phone(phone)
            route_text=str(route or '')
            if not resolved_phone and '@lid' not in route_text.lower():
                resolved_phone=normalize_contact_phone(route_text.split('@',1)[0])
            if not resolved_phone:
                raise RuntimeError('WhatsApp no entregó el número telefónico real del cliente; se recibió un identificador interno LID.')"""
if old_resolved not in s:
    raise SystemExit("No se encontró resolved_phone de save_contact")
s=s.replace(old_resolved,new_resolved,1)

# Extra safety in local contact storage.
old_phone_check="""    phone=normalize_contact_phone(phone)
    if not phone:
        raise RuntimeError('No se pudo obtener el número del cliente para guardar el contacto.')"""
new_phone_check="""    phone=normalize_contact_phone(phone)
    if not phone:
        raise RuntimeError('No se pudo obtener el número del cliente para guardar el contacto.')
    if len(phone)<7 or len(phone)>15:
        raise RuntimeError('El identificador recibido no parece un número telefónico válido.')"""
if old_phone_check not in s:
    raise SystemExit("No se encontró validación de save_customer_contact")
s=s.replace(old_phone_check,new_phone_check,1)

# =========================================================
# GOOGLE DESTINATION ACCOUNT
# =========================================================
# Add identity scopes so the app can show the actual selected email.
s=s.replace(
    "GOOGLE_SCOPES = ['https://www.googleapis.com/auth/contacts']",
    "GOOGLE_SCOPES = ['https://www.googleapis.com/auth/contacts','openid','https://www.googleapis.com/auth/userinfo.email']",
    1
)

# Track which Google account owns google_resource.
migration = r'''
def ensure_google_account_column():
    with DB_LOCK, db() as con:
        cols={r['name'] for r in con.execute('PRAGMA table_info(contacts)').fetchall()}
        if 'google_account' not in cols:
            con.execute("ALTER TABLE contacts ADD COLUMN google_account TEXT NOT NULL DEFAULT ''")
        con.commit()

ensure_google_account_column()
'''
migration=textwrap.dedent(migration)
if "def ensure_google_account_column" not in s:
    anchor="ensure_google_contact_columns()\n"
    if anchor not in s:
        raise SystemExit("No se encontró ensure_google_contact_columns")
    s=s.replace(anchor,anchor+"\n"+migration+"\n",1)

status_block = r'''
def google_account_file(pid):
    return google_profile_dir(pid) / 'selected_account.json'

def google_selected_email(pid):
    p=google_account_file(pid)
    if not p.exists():
        return ''
    try:
        obj=json.loads(p.read_text('utf-8'))
        return str(obj.get('email') or '').strip()
    except Exception:
        return ''

def google_status(pid):
    client=google_client_file(pid)
    token=google_token_file(pid)
    email=google_selected_email(pid)
    return {
        'configured':client.exists(),
        'connected':token.exists() and client.exists(),
        'email':email,
        'needs_account_selection':bool(token.exists() and not email),
        'client_file':str(client),
        'token_file':str(token),
    }
'''
status_block=textwrap.dedent(status_block)
s,n=re.subn(
    r"def google_status\(pid\):.*?(?=\ndef google_disconnect\(pid\):)",
    lambda _m:status_block.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar google_status")

disconnect_block = r'''
def google_disconnect(pid):
    token=google_token_file(pid)
    if token.exists():
        try:token.unlink()
        except Exception:pass
    account=google_account_file(pid)
    if account.exists():
        try:account.unlink()
        except Exception:pass
'''
disconnect_block=textwrap.dedent(disconnect_block)
s,n=re.subn(
    r"def google_disconnect\(pid\):.*?(?=\ndef google_connect\(pid,)",
    lambda _m:disconnect_block.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar google_disconnect")

connect_block = r'''
def google_connect(pid, source_credentials_json=None):
    target=google_client_file(pid)

    if source_credentials_json:
        source=Path(source_credentials_json)
        if not source.exists():
            raise RuntimeError('No se encontró el archivo credentials.json.')
        try:
            raw=json.loads(source.read_text('utf-8'))
        except Exception as e:
            raise RuntimeError(f'El archivo seleccionado no es un JSON válido: {e}')
        if not isinstance(raw,dict) or ('installed' not in raw and 'web' not in raw):
            raise RuntimeError('El JSON no parece ser una credencial OAuth de Google.')
        shutil.copy2(source,target)
    elif not target.exists():
        raise RuntimeError('Primero selecciona credentials.json de Google.')

    old_email=google_selected_email(pid)

    flow=InstalledAppFlow.from_client_secrets_file(str(target),GOOGLE_SCOPES)
    creds=flow.run_local_server(
        port=0,
        open_browser=True,
        prompt='consent select_account',
        authorization_prompt_message='Selecciona la cuenta de Google que recibirá automáticamente los contactos de este negocio.'
    )

    email=''
    try:
        token_info=getattr(creds,'id_token',None)
        if isinstance(token_info,dict):
            email=str(token_info.get('email') or '').strip()
    except Exception:
        email=''

    if not email:
        try:
            identity=google_build('oauth2','v2',credentials=creds,cache_discovery=False)
            profile=identity.userinfo().get().execute()
            email=str(profile.get('email') or '').strip()
        except Exception as e:
            raise RuntimeError(f'Google autorizó la cuenta, pero no se pudo identificar el correo seleccionado: {e}')

    if not email:
        raise RuntimeError('Google no devolvió el correo de la cuenta seleccionada.')

    google_token_file(pid).write_text(creds.to_json(),encoding='utf-8')
    google_account_file(pid).write_text(
        json.dumps(
            {'email':email,'selected_at':datetime.now().isoformat(timespec='seconds')},
            ensure_ascii=False,indent=2
        ),
        encoding='utf-8'
    )

    # Resource names belong to one Google account. If destination changes,
    # reset only Google sync metadata; local contacts remain untouched.
    if old_email.lower()!=email.lower():
        x(
            "UPDATE contacts SET google_resource='',google_synced_at='',google_error='',google_account='' "
            "WHERE profile_id=?",
            (pid,)
        )

    log(pid,'info',f'Cuenta Google destino seleccionada · {email}')
    return {'email':email}
'''
connect_block=textwrap.dedent(connect_block)
s,n=re.subn(
    r"def google_connect\(pid, source_credentials_json\):.*?(?=\ndef google_credentials\(pid\):)",
    lambda _m:connect_block.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar google_connect")

credentials_block = r'''
def google_credentials(pid):
    token=google_token_file(pid)
    client=google_client_file(pid)
    if not token.exists() or not client.exists():
        return None
    try:
        # Load the scopes stored in the token itself. This keeps old installations
        # readable until the user chooses/reconnects an account with identity scope.
        creds=Credentials.from_authorized_user_file(str(token))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token.write_text(creds.to_json(),encoding='utf-8')
        if not creds.valid:
            return None
        return creds
    except Exception:
        return None
'''
credentials_block=textwrap.dedent(credentials_block)
s,n=re.subn(
    r"def google_credentials\(pid\):.*?(?=\ndef google_service\(pid\):)",
    lambda _m:credentials_block.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar google_credentials")

sync_block = r'''
def google_sync_contact(cid):
    row=get_contact(cid)
    if not row:
        return False
    pid=row['profile_id']
    st=google_status(pid)
    if not st.get('connected'):
        return False
    target_email=str(st.get('email') or '').strip()
    with GOOGLE_LOCK:
        try:
            service=google_service(pid)
            saved_account=str(row.get('google_account') or '').strip()
            resource=''
            if not target_email or saved_account.lower()==target_email.lower():
                resource=str(row.get('google_resource') or '')

            if not resource:
                resource=_google_find_phone(service,row.get('phone') or '')

            if not resource:
                body={
                    'names':[{'givenName':row.get('name') or ('Cliente '+str(row.get('phone') or '')[-4:])}],
                    'phoneNumbers':[{'value':'+'+_digits(row.get('phone') or '')}],
                }
                note=str(row.get('note') or '').strip()
                label=str(row.get('label') or '').strip()
                if note:
                    body['biographies']=[{'value':note,'contentType':'TEXT_PLAIN'}]
                if label:
                    body['userDefined']=[{'key':'Etiqueta','value':label}]
                created=service.people().createContact(
                    body=body,
                    personFields='names,phoneNumbers,userDefined,biographies'
                ).execute()
                resource=created.get('resourceName') or ''

            x(
                "UPDATE contacts SET google_resource=?,google_synced_at=?,google_error='',google_account=? WHERE id=?",
                (
                    resource,
                    datetime.now().isoformat(timespec='seconds'),
                    target_email,
                    int(cid)
                )
            )
            suffix=f' → {target_email}' if target_email else ''
            log(pid,'info',f'Contacto sincronizado con Google{suffix} · {row.get("phone") or ""}')
            return True
        except Exception as e:
            x("UPDATE contacts SET google_error=? WHERE id=?",(str(e)[:500],int(cid)))
            suffix=f' ({target_email})' if target_email else ''
            log(pid,'error',f'Google Contacts{suffix}: {e}')
            return False
'''
sync_block=textwrap.dedent(sync_block)
s,n=re.subn(
    r"def google_sync_contact\(cid\):.*?(?=\ndef google_sync_contact_async\(cid\):)",
    lambda _m:sync_block.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar google_sync_contact")

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# =========================================================
# GUI: explicit Google destination email and diagnostics
# =========================================================
g=gui_path.read_text(encoding="utf-8")

google_methods = r'''
    def refresh_google_contacts_status(self):
        if not hasattr(self,'google_contacts_status'):
            return
        pid=self.pid()
        if not pid:
            self.google_contacts_status.set('Sin negocio seleccionado')
            if hasattr(self,'google_target_email'):
                self.google_target_email.set('No seleccionada')
            return
        st=C.google_status(pid)
        email=str(st.get('email') or '').strip()
        if hasattr(self,'google_target_email'):
            self.google_target_email.set(email or 'No seleccionada')
        if st.get('connected') and email:
            self.google_contacts_status.set('SINCRONIZACIÓN AUTOMÁTICA ACTIVA')
        elif st.get('connected'):
            self.google_contacts_status.set('Cuenta anterior conectada · vuelve a seleccionar el correo para identificarla')
        elif st.get('configured'):
            self.google_contacts_status.set('Google configurado · falta seleccionar la cuenta destino')
        else:
            self.google_contacts_status.set('Google no configurado')

    def connect_google_contacts(self):
        pid=self.pid()
        if not pid:return
        st=C.google_status(pid)
        path=None
        if not st.get('configured'):
            path=filedialog.askopenfilename(
                parent=self,
                title='Selecciona credentials.json de Google',
                filetypes=[('JSON de Google','*.json'),('Todos los archivos','*.*')]
            )
            if not path:return
        try:
            result=C.google_connect(pid,path)
            self.refresh_google_contacts_status()
            email=(result or {}).get('email') or C.google_status(pid).get('email') or ''
            messagebox.showinfo(
                'Cuenta Google destino',
                f'Cuenta seleccionada:\n{email}\n\nLos contactos nuevos se guardarán automáticamente en esta cuenta. '
                'Ahora se sincronizarán también los contactos locales pendientes.',
                parent=self
            )
            self.sync_all_google_contacts()
        except Exception as e:
            messagebox.showerror('Cuenta Google destino',str(e),parent=self)

    def disconnect_google_contacts(self):
        pid=self.pid()
        if not pid:return
        email=C.google_status(pid).get('email') or 'la cuenta actual'
        if not messagebox.askyesno(
            'Desconectar Google',
            f'¿Desconectar {email}?\n\nLos contactos seguirán guardándose dentro de Monopolio MultiBot.',
            parent=self
        ):
            return
        C.google_disconnect(pid)
        self.refresh_google_contacts_status()
        messagebox.showinfo('Google Contacts','Cuenta desconectada. El guardado local permanece activo.',parent=self)

    def sync_all_google_contacts(self):
        pid=self.pid()
        if not pid:return
        st=C.google_status(pid)
        if not st.get('connected'):
            return messagebox.showinfo('Google Contacts','Primero selecciona la cuenta Google destino.',parent=self)
        def worker():
            ok,total=C.google_sync_all(pid)
            self.after(0,self.refresh_contacts)
            self.after(0,self.refresh_google_contacts_status)
            self.after(
                0,
                lambda:messagebox.showinfo(
                    'Google Contacts',
                    f'Sincronización terminada: {ok} de {total} contactos.\nDestino: {C.google_status(pid).get("email") or "cuenta conectada"}',
                    parent=self
                )
            )
        threading.Thread(target=worker,daemon=True,name='google-sync-all').start()

    def open_google_setup_help(self):
        webbrowser.open('https://developers.google.com/people/quickstart/python')
'''
google_methods=textwrap.indent(textwrap.dedent(google_methods).strip()+"\n","    ")
g,n=re.subn(
    r"    def refresh_google_contacts_status\(self\):.*?(?=\n    def build_contacts\(self\):)",
    lambda _m:google_methods.rstrip()+"\n",
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar métodos Google de GUI")

google_box = r'''
        google=ttk.LabelFrame(f,text='Cuenta Google destino',padding=10)
        google.pack(fill='x',pady=(0,10))

        row1=ttk.Frame(google)
        row1.pack(fill='x')
        ttk.Label(row1,text='Correo que recibirá los contactos:',font=('Segoe UI',10,'bold')).pack(side='left')
        self.google_target_email=tk.StringVar(value='No seleccionada')
        ttk.Entry(
            row1,textvariable=self.google_target_email,state='readonly',width=42
        ).pack(side='left',padx=(8,8))
        ttk.Button(
            row1,text='Seleccionar / cambiar cuenta',
            command=self.connect_google_contacts
        ).pack(side='left')

        row2=ttk.Frame(google)
        row2.pack(fill='x',pady=(8,0))
        self.google_contacts_status=tk.StringVar(value='Google no configurado')
        ttk.Label(
            row2,textvariable=self.google_contacts_status,foreground=MUTED
        ).pack(side='left')
        ttk.Button(row2,text='Sincronizar pendientes',command=self.sync_all_google_contacts).pack(side='right',padx=5)
        ttk.Button(row2,text='Desconectar',command=self.disconnect_google_contacts).pack(side='right')
        ttk.Button(row2,text='Guía Google',command=self.open_google_setup_help).pack(side='right',padx=5)
        self.refresh_google_contacts_status()
'''
google_box=textwrap.indent(textwrap.dedent(google_box).strip()+"\n","    ")
g,n=re.subn(
    r"        google=ttk\.LabelFrame\(f,text='Google Contacts \(opcional\)'.*?        self\.refresh_google_contacts_status\(\)\n",
    lambda _m:google_box,
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar bloque Google en Contactos")

# Add a visible per-contact Google status column.
g=g.replace(
    "cols=('name','phone','label','last','rule','count')",
    "cols=('name','phone','label','last','rule','google','count')",
    1
)
g=g.replace(
    "('rule','Regla',220),('count','Veces',65)",
    "('rule','Regla',190),('google','Google',150),('count','Veces',65)",
    1
)

old_insert="""                      self.contacts_tree.insert('', 'end', iid=str(row['id']), values=(row.get('name') or '',row.get('phone') or '',row.get('label') or '',row.get('last_seen') or '',row.get('last_rule') or '',row.get('interactions') or 0))"""
new_insert="""                      if row.get('google_synced_at'):
                          google_state='✓ Sincronizado'
                      elif row.get('google_error'):
                          google_state='⚠ Error'
                      else:
                          google_state='Pendiente'
                      self.contacts_tree.insert(
                          '', 'end', iid=str(row['id']),
                          values=(
                              row.get('name') or '',
                              row.get('phone') or '',
                              row.get('label') or '',
                              row.get('last_seen') or '',
                              row.get('last_rule') or '',
                              google_state,
                              row.get('interactions') or 0
                          )
                      )"""
if old_insert not in g:
    raise SystemExit("No se encontró inserción de contactos")
g=g.replace(old_insert,new_insert,1)

# Clarify save_contact action behavior for the user.
g=g.replace(
    "Cuando esta regla coincida, el número del cliente se guardará en Contactos. Si ya existe, se omite y no se modifica. Si Google Contacts está conectado, solo los contactos nuevos se sincronizan.",
    "Cuando esta regla coincida, se guardará primero el número telefónico real del cliente en Contactos. "
    "Si seleccionaste una Cuenta Google destino, cada contacto nuevo se sincronizará automáticamente con ese correo. "
    "Los identificadores internos LID de WhatsApp no se guardarán como teléfonos.",
    1
)

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# =========================================================
# INSTALLER
# =========================================================
t=iss_path.read_text(encoding="utf-8")
if "2.2.2" not in t and "2.2.3" not in t:
    raise SystemExit("No se encontró versión 2.2.2 en installer.iss")
t=t.replace("2.2.2","2.2.3")
iss_path.write_text(t,encoding="utf-8")
