import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
gui_path=root/"gui_local.py"
iss_path=root/"installer.iss"

# =========================================================
# CORE
# =========================================================
s=core_path.read_text(encoding="utf-8")
s=s.replace("APP_VERSION = '2.1.2'","APP_VERSION = '2.2.0'")

# ---------- Días seleccionados en Estados ----------
week_migration = r'''
def ensure_schedule_weekdays_column():
    with DB_LOCK, db() as con:
        cols={r['name'] for r in con.execute('PRAGMA table_info(schedules)').fetchall()}
        if 'weekdays' not in cols:
            con.execute("ALTER TABLE schedules ADD COLUMN weekdays TEXT NOT NULL DEFAULT ''")
        con.commit()

ensure_schedule_weekdays_column()
'''
week_migration=textwrap.dedent(week_migration)
if "def ensure_schedule_weekdays_column" not in s:
    anchor="ensure_schedule_media_columns()\n"
    if anchor not in s:
        raise SystemExit("No se encontró migración de schedules")
    s=s.replace(anchor,anchor+"\n"+week_migration+"\n",1)

save_schedule = r'''
def save_schedule(pid,d):
    kind=str(d.get('kind') or 'status_text')
    if kind not in ('status_text','status_image','status_video'):
        kind='status_text'
    recurrence=str(d.get('recurrence') or 'once')
    if recurrence not in ('once','daily','selected_days'):
        recurrence='once'
    try:
        media_id=int(d.get('media_id') or 0)
    except Exception:
        media_id=0
    weekdays=str(d.get('weekdays') or '').strip()
    vals=(
        kind,
        str(d.get('run_date') or ''),
        str(d.get('run_time') or '12:00'),
        recurrence,
        str(d.get('text') or ''),
        media_id,
        weekdays,
        1 if d.get('active',True) else 0,
    )
    if d.get('id'):
        x(
            'UPDATE schedules SET kind=?,run_date=?,run_time=?,recurrence=?,text=?,media_id=?,weekdays=?,active=? '
            'WHERE id=? AND profile_id=?',
            vals+(int(d['id']),pid)
        )
        return int(d['id'])
    return x(
        'INSERT INTO schedules(profile_id,kind,run_date,run_time,recurrence,text,media_id,weekdays,active) '
        'VALUES(?,?,?,?,?,?,?,?,?)',
        (pid,)+vals
    )
'''
save_schedule=textwrap.dedent(save_schedule)
s,n=re.subn(
    r"def save_schedule\(pid,d\):.*?(?=\ndef delete_schedule\(sid\):)",
    lambda _m:save_schedule.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo actualizar save_schedule")

new_scheduler = r'''
def scheduler_loop():
    while ENGINE.running:
        try:
            now=datetime.now()
            today=now.strftime('%Y-%m-%d')
            hm=now.strftime('%H:%M')
            weekday=str(now.weekday())
            for item in q('SELECT * FROM schedules WHERE active=1'):
                due=False
                recurrence=item.get('recurrence') or 'once'
                if recurrence=='daily':
                    due=(hm>=item['run_time'] and item['last_run']!=today)
                elif recurrence=='selected_days':
                    selected={x.strip() for x in str(item.get('weekdays') or '').split(',') if x.strip()}
                    due=(weekday in selected and hm>=item['run_time'] and item['last_run']!=today)
                else:
                    due=(item['run_date']<=today and hm>=item['run_time'] and item['last_run']!=today)
                if not due:
                    continue
                try:
                    publish_whatsapp_status(
                        item['profile_id'],
                        item.get('kind') or 'status_text',
                        item.get('text') or '',
                        int(item.get('media_id') or 0),
                    )
                    x(
                        'UPDATE schedules SET last_run=?,active=? WHERE id=?',
                        (today,1 if recurrence in ('daily','selected_days') else 0,item['id'])
                    )
                    log(item['profile_id'],'info','Estado de WhatsApp publicado correctamente')
                except Exception as e:
                    log(item['profile_id'],'error',f'Error publicando estado de WhatsApp: {e}')
        except Exception as e:
            log('','error',f'Error en programador de estados: {e}')
        time.sleep(10)
'''
new_scheduler=textwrap.dedent(new_scheduler)
s,n=re.subn(
    r"def scheduler_loop\(\):.*?(?=\n\n\ndef start_services\(\):)",
    lambda _m:new_scheduler.rstrip(),
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo actualizar scheduler_loop")

# ---------- País/bandera automática ----------
country_helpers = r'''
COUNTRY_PREFIXES = [
    ('593','EC','🇪🇨','Ecuador'),
    ('57','CO','🇨🇴','Colombia'),
    ('52','MX','🇲🇽','México'),
    ('34','ES','🇪🇸','España'),
    ('51','PE','🇵🇪','Perú'),
    ('1','US','🇺🇸','Estados Unidos'),
]

def detect_country_from_phone(phone):
    digits=re.sub(r'\D+','',str(phone or ''))
    for prefix,code,flag,name in COUNTRY_PREFIXES:
        if digits.startswith(prefix):
            return {'prefix':prefix,'code':code,'flag':flag,'name':name}
    return {'prefix':'','code':'','flag':'','name':''}

def country_flag_for_phone(phone):
    return detect_country_from_phone(phone).get('flag') or ''

def country_name_for_phone(phone):
    return detect_country_from_phone(phone).get('name') or ''
'''
country_helpers=textwrap.dedent(country_helpers)
if "COUNTRY_PREFIXES = [" not in s:
    anchor="def normalize_contact_phone(phone):"
    pos=s.find(anchor)
    if pos<0:
        raise SystemExit("No se encontró normalize_contact_phone")
    s=s[:pos]+country_helpers+"\n\n"+s[pos:]

# Variables @pais y @bandera.
vars_method = r'''
    def vars(self,s,phone,name,msg):
        now=datetime.now()
        country=detect_country_from_phone(phone)
        return (
            str(s or '')
            .replace('@mensaje',msg or '')
            .replace('@telefono',phone or '')
            .replace('@nombre',name or '')
            .replace('@hora',now.strftime('%H:%M'))
            .replace('@dia',now.strftime('%A'))
            .replace('@fecha_completa',now.strftime('%d/%m/%Y %H:%M'))
            .replace('@pais',country.get('name') or '')
            .replace('@bandera',country.get('flag') or '')
        )
'''
vars_method=textwrap.dedent(vars_method)
vars_method=textwrap.indent(vars_method,"    ")
s,n=re.subn(
    r"    def vars\(self,s,phone,name,msg\):.*?(?=\n    def action_media_value\(self,a,kind=''\):)",
    lambda _m:vars_method.rstrip(),
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo actualizar Engine.vars")

# Añadir bandera al guardar contacto cuando la acción lo pida.
flag_anchor="""            if not display_name:
                display_name=(name or '').strip()
                if not display_name:
                    display_name=f'Cliente {resolved_phone[-4:]}' if resolved_phone else 'Cliente'
            label=self.vars(a.get('label') or 'Cliente',phone,name,msg).strip()
"""
flag_repl="""            if not display_name:
                display_name=(name or '').strip()
                if not display_name:
                    display_name=f'Cliente {resolved_phone[-4:]}' if resolved_phone else 'Cliente'
            if a.get('auto_country_flag'):
                flag=country_flag_for_phone(resolved_phone)
                if flag and not display_name.startswith(flag):
                    display_name=f'{flag} {display_name}'
            label=self.vars(a.get('label') or 'Cliente',phone,name,msg).strip()
"""
if flag_anchor not in s:
    raise SystemExit("No se encontró bloque save_contact para bandera")
s=s.replace(flag_anchor,flag_repl,1)

# ---------- Modo asesor/handoff ----------
handoff_migration = r'''
def ensure_handoff_table():
    with DB_LOCK, db() as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS paused_contacts("
            "profile_id TEXT NOT NULL, phone TEXT NOT NULL, paused_at TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',"
            "PRIMARY KEY(profile_id,phone))"
        )
        con.commit()

ensure_handoff_table()

def pause_contact(profile_id,phone,reason=''):
    phone=normalize_contact_phone(phone)
    if not phone:
        raise RuntimeError('No se pudo identificar el número del cliente.')
    x(
        'INSERT OR REPLACE INTO paused_contacts(profile_id,phone,paused_at,reason) VALUES(?,?,?,?)',
        (profile_id,phone,datetime.now().isoformat(timespec='seconds'),str(reason or '')[:300])
    )

def resume_contact(profile_id,phone):
    phone=normalize_contact_phone(phone)
    x('DELETE FROM paused_contacts WHERE profile_id=? AND phone=?',(profile_id,phone))

def is_contact_paused(profile_id,phone):
    phone=normalize_contact_phone(phone)
    if not phone:return False
    return q('SELECT profile_id FROM paused_contacts WHERE profile_id=? AND phone=?',(profile_id,phone),one=True) is not None
'''
handoff_migration=textwrap.dedent(handoff_migration)
if "def ensure_handoff_table" not in s:
    anchor="def recent_logs(pid=None,limit=400):"
    pos=s.find(anchor)
    if pos<0:
        raise SystemExit("No se encontró recent_logs para handoff")
    s=s[:pos]+handoff_migration+"\n\n"+s[pos:]

# Acción human_handoff.
handoff_action = """        if typ=='human_handoff':
            reason=self.vars(a.get('reason') or 'Cliente solicitó hablar con el equipo',phone,name,msg)
            pause_contact(pid,phone or str(route).split('@',1)[0],reason)
            log(pid,'info',f'Modo asesor activado · {phone or route}')
            return

"""
action_anchor="        if typ=='text':\n"
pos=s.find(action_anchor,s.find("def execute_action"))
if pos<0:
    raise SystemExit("No se encontró execute_action para handoff")
if "if typ=='human_handoff':" not in s:
    s=s[:pos]+handoff_action+s[pos:]

# Ignorar mensajes futuros del cliente cuando está en modo asesor.
webhook_anchor="""            phone=self.phone(alt,sender,chat); name=str(info.get('PushName') or info.get('pushName') or '')
            m=d.get('Message') or d.get('message') or {}; text=(self.extract_text(m) or str(d.get('text') or root.get('message') or '')).strip()
"""
webhook_repl="""            phone=self.phone(alt,sender,chat); name=str(info.get('PushName') or info.get('pushName') or '')
            if is_contact_paused(pid,phone):
                log(pid,'info',f'Mensaje recibido en modo asesor · {phone or route}')
                return
            m=d.get('Message') or d.get('message') or {}; text=(self.extract_text(m) or str(d.get('text') or root.get('message') or '')).strip()
"""
if webhook_anchor not in s:
    raise SystemExit("No se encontró punto de pausa en webhook")
s=s.replace(webhook_anchor,webhook_repl,1)

# Templates accept human_handoff.
s=s.replace(
    "'location','contact','save_contact','buttons','list'",
    "'location','contact','save_contact','human_handoff','buttons','list'"
)

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# =========================================================
# GUI
# =========================================================
g=gui_path.read_text(encoding="utf-8")

# Fix actual Tk error: family name contains a space.
g=g.replace("self.option_add('*Font','Segoe UI 10')","self.option_add('*Font','{Segoe UI} 10')")

# Labels.
g=g.replace(
    "'save_contact':'Guardar cliente',",
    "'save_contact':'Guardar cliente',\n    'human_handoff':'Pasar a asesor',"
)
g=g.replace(
    "RECURRENCE_LABELS = {'once':'Una sola vez','daily':'Todos los días'}",
    "RECURRENCE_LABELS = {'once':'Una sola vez','daily':'Todos los días','selected_days':'Días seleccionados'}"
)
g=g.replace(
    "TYPES=['text','image','video','audio','document','sticker','location','contact','save_contact','buttons','list']",
    "TYPES=['text','image','video','audio','document','sticker','location','contact','save_contact','human_handoff','buttons','list']"
)

# Save-contact UI: checkbox bandera.
save_contact_note = """            nt.insert('1.0',self.v.get('note',''))
            self.widgets['note']=nt
            ttk.Label(
                self.body,
                text='Variables disponibles: @nombre, @telefono, @mensaje, @hora, @dia, @fecha_completa.',
                foreground=MUTED
            ).pack(anchor='w',pady=8)
"""
save_contact_note_repl = """            nt.insert('1.0',self.v.get('note',''))
            self.widgets['note']=nt
            auto_flag=tk.BooleanVar(value=bool(self.v.get('auto_country_flag',False)))
            self.widgets['auto_country_flag']=auto_flag
            ttk.Checkbutton(
                self.body,
                text='Agregar bandera automática según el código del país',
                variable=auto_flag
            ).pack(anchor='w',pady=(8,2))
            ttk.Label(
                self.body,
                text='Variables disponibles: @nombre, @telefono, @mensaje, @hora, @dia, @fecha_completa, @pais y @bandera.',
                foreground=MUTED
            ).pack(anchor='w',pady=8)
"""
if save_contact_note not in g:
    raise SystemExit("No se encontró UI save_contact")
g=g.replace(save_contact_note,save_contact_note_repl,1)

# UI de handoff.
handoff_ui = r'''
        if typ=='human_handoff':
            ttk.Label(self.body,text='PASAR CON UN ASESOR',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(2,8))
            ttk.Label(
                self.body,
                text='Después de esta acción el bot deja de responder automáticamente a este cliente. '
                     'La conversación queda disponible para que una persona del equipo continúe desde WhatsApp. '
                     'Puedes reactivar el bot desde la pestaña Contactos.',
                wraplength=700,foreground=MUTED
            ).pack(anchor='w',pady=(0,12))
            r=ttk.Frame(self.body);r.pack(fill='x',pady=5)
            ttk.Label(r,text='Motivo',width=25).pack(side='left')
            sv=tk.StringVar(value=self.v.get('reason','Cliente solicitó hablar con el equipo'))
            self.widgets['reason']=sv
            ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)

'''
anchor="        if typ in ('buttons','list'):\n"
pos=g.find(anchor,g.find("class ActionDialog"))
if pos<0:
    raise SystemExit("No se encontró ancla de ActionDialog para handoff")
if "if typ=='human_handoff':" not in g:
    g=g[:pos]+handoff_ui+g[pos:]

# BooleanVar-safe action serialization.
old_loop="""        for k,w in self.widgets.items():
            if isinstance(w,tk.Text):
                d[k]=w.get('1.0','end').strip()
            else:
                d[k]=w.get().strip()
"""
new_loop="""        for k,w in self.widgets.items():
            if isinstance(w,tk.Text):
                d[k]=w.get('1.0','end').strip()
            else:
                value=w.get()
                d[k]=value.strip() if isinstance(value,str) else value
"""
if old_loop not in g:
    raise SystemExit("No se encontró serialización de widgets")
g=g.replace(old_loop,new_loop,1)

# ---------- Programación por días ----------
new_refresh_status = r'''
    def refresh_status(self):
        if not hasattr(self,'status_tree'):
            return
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)
        pid=self.pid()
        if not pid:return

        day_names={'0':'Lun','1':'Mar','2':'Mié','3':'Jue','4':'Vie','5':'Sáb','6':'Dom'}
        for item in C.schedules_for(pid):
            date=item.get('run_date') or ''
            try:
                date_show=datetime.strptime(date,'%Y-%m-%d').strftime('%d/%m/%Y')
            except Exception:
                date_show=date
            kind=item.get('kind') or 'status_text'
            text=(item.get('text') or '').strip()
            media_name=self._status_media_name(item.get('media_id') or 0)
            if kind=='status_text':
                content=text
            else:
                content=media_name + (f' · {text}' if text else '')

            rec=item.get('recurrence') or 'once'
            if rec=='selected_days':
                selected=[x.strip() for x in str(item.get('weekdays') or '').split(',') if x.strip()]
                rec_show=', '.join(day_names.get(x,x) for x in selected) or 'Días seleccionados'
            else:
                rec_show=RECURRENCE_LABELS.get(rec,'Una sola vez')

            self.status_tree.insert(
                '', 'end', iid=str(item['id']),
                values=(
                    STATUS_KIND_LABELS.get(kind,kind),
                    date_show if rec=='once' else '—',
                    item.get('run_time') or '',
                    rec_show,
                    content[:180],
                    'Sí' if item.get('active') else 'No'
                )
            )
'''
new_refresh_status=textwrap.dedent(new_refresh_status)
new_refresh_status=textwrap.indent(new_refresh_status,"    ")
g,n=re.subn(
    r"    def refresh_status\(self\):.*?(?=\n    def status_dialog\(self,val=None\):)",
    lambda _m:new_refresh_status.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar refresh_status")

new_status_dialog = r'''
    def status_dialog(self,val=None):
        v=val or {}
        win=tk.Toplevel(self)
        win.title('Programar estado de WhatsApp')
        win.transient(self)
        win.grab_set()
        win.resizable(False,False)
        f=ttk.Frame(win,padding=18)
        f.pack(fill='both',expand=True)

        kind_internal=v.get('kind') or 'status_text'
        kind=tk.StringVar(value=STATUS_KIND_LABELS.get(kind_internal,'Solo texto'))
        date=tk.StringVar(value=v.get('run_date') or datetime.now().strftime('%Y-%m-%d'))

        current_time=v.get('run_time') or datetime.now().strftime('%H:%M')
        try:hh,mm=current_time.split(':',1)
        except Exception:hh,mm='12','00'
        hour=tk.StringVar(value=hh)
        minute=tk.StringVar(value=mm)

        rec=tk.StringVar(value=RECURRENCE_LABELS.get(v.get('recurrence') or 'once','Una sola vez'))
        active=tk.BooleanVar(value=bool(v.get('active',1)))
        selected_existing={x.strip() for x in str(v.get('weekdays') or '').split(',') if x.strip()}
        day_vars={str(i):tk.BooleanVar(value=str(i) in selected_existing) for i in range(7)}

        ttk.Label(f,text='Tipo de publicación').grid(row=0,column=0,sticky='w',pady=6)
        kind_cb=ttk.Combobox(f,textvariable=kind,values=list(STATUS_KIND_LABELS.values()),state='readonly',width=28)
        kind_cb.grid(row=0,column=1,columnspan=2,sticky='ew',pady=6)

        ttk.Label(f,text='Fecha').grid(row=1,column=0,sticky='w',pady=6)
        date_entry=ttk.Entry(f,textvariable=date,state='readonly',width=20)
        date_entry.grid(row=1,column=1,sticky='ew',pady=6)
        def choose_date():
            selected=self.pick_date_dialog(date.get())
            if selected:date.set(selected)
        date_button=ttk.Button(f,text='Escoger fecha',command=choose_date)
        date_button.grid(row=1,column=2,padx=(6,0),pady=6)

        ttk.Label(f,text='Hora').grid(row=2,column=0,sticky='w',pady=6)
        time_box=ttk.Frame(f);time_box.grid(row=2,column=1,columnspan=2,sticky='w',pady=6)
        ttk.Spinbox(time_box,from_=0,to=23,textvariable=hour,width=5,format='%02.0f').pack(side='left')
        ttk.Label(time_box,text=':').pack(side='left',padx=3)
        ttk.Spinbox(time_box,from_=0,to=59,textvariable=minute,width=5,format='%02.0f').pack(side='left')

        ttk.Label(f,text='Repetición').grid(row=3,column=0,sticky='w',pady=6)
        rec_cb=ttk.Combobox(f,textvariable=rec,values=list(RECURRENCE_LABELS.values()),state='readonly',width=28)
        rec_cb.grid(row=3,column=1,columnspan=2,sticky='ew',pady=6)

        days_box=ttk.LabelFrame(f,text='Días de publicación',padding=8)
        days_box.grid(row=4,column=0,columnspan=3,sticky='ew',pady=(2,8))
        day_labels=[('0','Lunes'),('1','Martes'),('2','Miércoles'),('3','Jueves'),('4','Viernes'),('5','Sábado'),('6','Domingo')]
        for idx,(code,label) in enumerate(day_labels):
            ttk.Checkbutton(days_box,text=label,variable=day_vars[code]).grid(row=idx//4,column=idx%4,sticky='w',padx=6,pady=3)

        ttk.Label(f,text='Archivo').grid(row=5,column=0,sticky='w',pady=6)
        media=tk.StringVar()
        media_values=[f"{m['id']} | {m['name']}" for m in C.media_list()]
        old_mid=int(v.get('media_id') or 0)
        if old_mid:
            media.set(next((x for x in media_values if x.startswith(str(old_mid)+' | ')),''))
        media_cb=ttk.Combobox(f,textvariable=media,values=media_values,state='readonly',width=48)
        media_cb.grid(row=5,column=1,columnspan=2,sticky='ew',pady=6)

        text_label=ttk.Label(f,text='Texto')
        text_label.grid(row=6,column=0,sticky='nw',pady=6)
        txt=tk.Text(f,width=55,height=7,wrap='word')
        txt.grid(row=6,column=1,columnspan=2,pady=6)
        txt.insert('1.0',v.get('text',''))

        ttk.Checkbutton(f,text='Programación activa',variable=active).grid(
            row=7,column=1,columnspan=2,sticky='w',pady=(5,10)
        )

        def update_kind(*_):
            internal=STATUS_KIND_BY_LABEL.get(kind.get(),'status_text')
            if internal=='status_text':
                media_cb.configure(state='disabled')
                text_label.configure(text='Texto del estado')
            else:
                media_cb.configure(state='readonly')
                text_label.configure(text='Pie de publicación (opcional)')

        def update_recurrence(*_):
            internal=RECURRENCE_BY_LABEL.get(rec.get(),'once')
            if internal=='once':
                date_entry.configure(state='readonly')
                date_button.configure(state='normal')
                for child in days_box.winfo_children():child.configure(state='disabled')
            elif internal=='selected_days':
                date_entry.configure(state='disabled')
                date_button.configure(state='disabled')
                for child in days_box.winfo_children():child.configure(state='normal')
            else:
                date_entry.configure(state='disabled')
                date_button.configure(state='disabled')
                for child in days_box.winfo_children():child.configure(state='disabled')

        kind_cb.bind('<<ComboboxSelected>>',update_kind)
        rec_cb.bind('<<ComboboxSelected>>',update_recurrence)
        update_kind();update_recurrence()

        out={}
        def save():
            internal=STATUS_KIND_BY_LABEL.get(kind.get(),'status_text')
            recurrence=RECURRENCE_BY_LABEL.get(rec.get(),'once')
            try:
                h=max(0,min(23,int(hour.get())))
                m=max(0,min(59,int(minute.get())))
            except Exception:
                return messagebox.showwarning('Hora inválida','Escoge una hora válida.',parent=win)

            weekdays=','.join(code for code,var in day_vars.items() if var.get())
            if recurrence=='selected_days' and not weekdays:
                return messagebox.showwarning('Faltan los días','Selecciona por lo menos un día de publicación.',parent=win)

            media_id=0
            if media.get():
                try:media_id=int(media.get().split('|',1)[0].strip())
                except Exception:media_id=0
            body=txt.get('1.0','end').strip()
            if internal=='status_text' and not body:
                return messagebox.showwarning('Falta el texto','Escribe el texto del estado.',parent=win)
            if internal in ('status_image','status_video') and not media_id:
                return messagebox.showwarning('Falta el archivo','Selecciona una imagen o video de la biblioteca.',parent=win)

            if media_id:
                try:
                    mime=C.media_mime(media_id)
                    if internal=='status_image' and not mime.startswith('image/'):
                        return messagebox.showwarning('Archivo incorrecto','Selecciona una imagen para este estado.',parent=win)
                    if internal=='status_video' and not mime.startswith('video/'):
                        return messagebox.showwarning('Archivo incorrecto','Selecciona un video para este estado.',parent=win)
                except Exception as e:
                    return messagebox.showwarning('Archivo',str(e),parent=win)

            out.update({
                'id':v.get('id'),
                'kind':internal,
                'run_date':date.get().strip(),
                'run_time':f'{h:02d}:{m:02d}',
                'recurrence':recurrence,
                'weekdays':weekdays,
                'text':body,
                'media_id':media_id,
                'active':active.get(),
            })
            win.destroy()

        buttons=ttk.Frame(f);buttons.grid(row=8,column=0,columnspan=3,sticky='e',pady=(6,0))
        ttk.Button(buttons,text='Cancelar',command=win.destroy).pack(side='right',padx=(5,0))
        ttk.Button(buttons,text='Guardar programación',command=save).pack(side='right')
        win.wait_window()
        return out or None
'''
new_status_dialog=textwrap.dedent(new_status_dialog)
new_status_dialog=textwrap.indent(new_status_dialog,"    ")
g,n=re.subn(
    r"    def status_dialog\(self,val=None\):.*?(?=\n    def add_status\(self\):)",
    lambda _m:new_status_dialog.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar status_dialog")

# ---------- Reactivar bot para un contacto ----------
methods = r'''
    def pause_selected_contact(self):
        cid=self.selected_contact_id()
        contact=C.get_contact(cid) if cid else None
        if not contact:return
        C.pause_contact(self.pid(),contact.get('phone') or '','Pausado manualmente desde Contactos')
        messagebox.showinfo('Contactos','El bot quedó pausado para este cliente. Un asesor puede continuar la conversación.',parent=self)

    def resume_selected_contact(self):
        cid=self.selected_contact_id()
        contact=C.get_contact(cid) if cid else None
        if not contact:return
        C.resume_contact(self.pid(),contact.get('phone') or '')
        messagebox.showinfo('Contactos','El bot quedó reactivado para este cliente.',parent=self)
'''
methods=textwrap.dedent(methods)
methods=textwrap.indent(methods,"    ")
anchor="    def copy_contact_number(self):\n"
pos=g.find(anchor)
if pos<0:
    raise SystemExit("No se encontró copy_contact_number")
if "def resume_selected_contact" not in g:
    g=g[:pos]+methods+g[pos:]

g=g.replace(
    "ttk.Button(b,text='Eliminar',command=self.remove_contact).pack(side='left')",
    "ttk.Button(b,text='Eliminar',command=self.remove_contact).pack(side='left');ttk.Button(b,text='Pasar a asesor',command=self.pause_selected_contact).pack(side='left',padx=(12,5));ttk.Button(b,text='Reactivar bot',command=self.resume_selected_contact).pack(side='left')"
)

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# Installer version
t=iss_path.read_text(encoding="utf-8")
t=t.replace("2.1.2","2.2.0")
iss_path.write_text(t,encoding="utf-8")
