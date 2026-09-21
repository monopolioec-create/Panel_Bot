import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
gui_path=root/"gui_local.py"
iss_path=root/"installer.iss"

# =========================================================
# VERSION
# =========================================================
s=core_path.read_text(encoding="utf-8")
if "APP_VERSION = '2.2.4'" not in s and "APP_VERSION = '2.3.0'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.2.4")
s=s.replace("APP_VERSION = '2.2.4'","APP_VERSION = '2.3.0'",1)

# =========================================================
# FRIENDLY NAME FALLBACK
# @nombre_cliente => WhatsApp name, or "Cliente" when missing
# =========================================================
if ".replace('@nombre_cliente'" not in s:
    anchor=".replace('@nombre',name or '')"
    if anchor not in s:
        raise SystemExit("No se encontró variable @nombre")
    s=s.replace(
        anchor,
        ".replace('@nombre_cliente',(name or '').strip() or 'Cliente')\n            "+anchor,
        1
    )

# =========================================================
# GUIDED MENU STATE
# One incorrect answer => warning + repeat menu.
# Further incorrect answers => silence until a valid option is selected.
# =========================================================
flow_helpers = r'''
def ensure_guided_flow_table():
    with DB_LOCK, db() as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS guided_flows("
            "profile_id TEXT NOT NULL,"
            "phone TEXT NOT NULL,"
            "flow_id TEXT NOT NULL DEFAULT 'main',"
            "action_json TEXT NOT NULL,"
            "invalid_count INTEGER NOT NULL DEFAULT 0,"
            "updated_at TEXT NOT NULL,"
            "PRIMARY KEY(profile_id,phone))"
        )
        con.commit()

ensure_guided_flow_table()

def guided_flow_get(profile_id,phone):
    phone=normalize_contact_phone(phone)
    if not phone:return None
    return q(
        'SELECT * FROM guided_flows WHERE profile_id=? AND phone=?',
        (profile_id,phone),one=True
    )

def guided_flow_set(profile_id,phone,action):
    phone=normalize_contact_phone(phone)
    if not phone:return
    flow_id=str((action or {}).get('flow_id') or 'main')[:100]
    payload=json.dumps(action or {},ensure_ascii=False)
    x(
        'INSERT OR REPLACE INTO guided_flows(profile_id,phone,flow_id,action_json,invalid_count,updated_at) '
        'VALUES(?,?,?,?,0,?)',
        (
            profile_id,phone,flow_id,payload,
            datetime.now().isoformat(timespec='seconds')
        )
    )

def guided_flow_clear(profile_id,phone):
    phone=normalize_contact_phone(phone)
    if phone:
        x('DELETE FROM guided_flows WHERE profile_id=? AND phone=?',(profile_id,phone))

def guided_flow_set_invalid(profile_id,phone,count):
    phone=normalize_contact_phone(phone)
    if phone:
        x(
            'UPDATE guided_flows SET invalid_count=?,updated_at=? WHERE profile_id=? AND phone=?',
            (
                max(0,int(count)),
                datetime.now().isoformat(timespec='seconds'),
                profile_id,phone
            )
        )

def _guided_norm(value):
    value=str(value or '').strip().casefold()
    value=re.sub(r'[\s\u00a0]+',' ',value)
    value=re.sub(r'^[\W_]+|[\W_]+$','',value,flags=re.UNICODE)
    return value

def guided_option_match(message,buttons):
    wanted=_guided_norm(message)
    if not wanted:return None
    for button in (buttons or []):
        if not isinstance(button,dict):continue
        candidates=[
            button.get('id'),
            button.get('text'),
            button.get('title'),
        ]
        aliases=button.get('aliases') or []
        if isinstance(aliases,str):
            aliases=[x.strip() for x in aliases.split(',') if x.strip()]
        candidates.extend(aliases if isinstance(aliases,list) else [])
        for candidate in candidates:
            if candidate and _guided_norm(candidate)==wanted:
                return button
    return None
'''
flow_helpers=textwrap.dedent(flow_helpers)
if "def ensure_guided_flow_table" not in s:
    anchor="def recent_logs(pid=None,limit=400):"
    pos=s.find(anchor)
    if pos<0:
        raise SystemExit("No se encontró recent_logs para flujo guiado")
    s=s[:pos]+flow_helpers+"\n\n"+s[pos:]

# =========================================================
# ENGINE: intercept active guided menu before normal rules
# =========================================================
intercept_method = r'''
    def guided_menu_intercept(self,pid,token,route,phone,name,text):
        state=guided_flow_get(pid,phone)
        if not state:
            return None

        try:
            action=json.loads(state.get('action_json') or '{}')
        except Exception:
            guided_flow_clear(pid,phone)
            return None

        buttons=action.get('buttons') or []
        choice=guided_option_match(text,buttons)
        if choice:
            guided_flow_clear(pid,phone)
            selected=str(choice.get('id') or choice.get('text') or '').strip()
            log(pid,'info',f'Opción válida de menú guiado · {phone} · {selected}')
            return selected

        try:
            invalid_count=int(state.get('invalid_count') or 0)
        except Exception:
            invalid_count=0
        try:
            max_invalid=max(0,int(action.get('max_invalid') if action.get('max_invalid') is not None else 1))
        except Exception:
            max_invalid=1

        # Only the first N invalid answers get a correction. After that the bot
        # waits silently for one of the valid options, avoiding frustrating loops.
        if invalid_count < max_invalid:
            invalid_text=self.vars(
                action.get('invalid_text') or
                'No pude relacionar tu respuesta con las opciones disponibles. '
                'Para continuar, selecciona una opción del menú.',
                phone,name,text
            )
            if invalid_text:
                c,j=WUZ.call(
                    token,'POST','/chat/send/text',
                    {'Phone':route,'Body':invalid_text},90
                )
                if c>=300 or (isinstance(j,dict) and j.get('success') is False):
                    raise RuntimeError(f'No se pudo enviar aviso de opción inválida: HTTP {c}')

            body=self.vars(action.get('text') or '',phone,name,text)
            title=self.vars(action.get('title') or '',phone,name,text)
            footer=self.vars(action.get('footer') or '',phone,name,text)
            payload={
                'Phone':route,
                'Body':body,
                'Title':title,
                'Footer':footer,
                'Buttons':buttons,
            }
            c,j=WUZ.call(token,'POST','/chat/send/buttons',payload,180)
            if c>=300 or (isinstance(j,dict) and j.get('success') is False):
                raise RuntimeError(f'No se pudo repetir el menú guiado: HTTP {c}')
            guided_flow_set_invalid(pid,phone,invalid_count+1)
            log(pid,'info',f'Respuesta inválida · menú repetido una vez · {phone}')
        else:
            log(pid,'info',f'Respuesta inválida ignorada · esperando opción válida · {phone}')

        return False
'''
intercept_method=textwrap.indent(textwrap.dedent(intercept_method).strip()+"\n","    ")
if "def guided_menu_intercept(self,pid,token,route,phone,name,text):" not in s:
    anchor="    def execute_action(self,pid,token,route,phone,name,msg,a,rule_name,started):\n"
    pos=s.find(anchor)
    if pos<0:
        raise SystemExit("No se encontró execute_action para insertar menú guiado")
    s=s[:pos]+intercept_method+"\n"+s[pos:]

# =========================================================
# ENGINE ACTION: send menu and arm the guard
# =========================================================
guided_action = r'''        if typ=='guided_menu':
            buttons=a.get('buttons') or []
            if not isinstance(buttons,list) or not buttons:
                raise RuntimeError('El menú guiado no tiene opciones.')
            body=self.vars(a.get('text') or '',phone,name,msg)
            title=self.vars(a.get('title') or '',phone,name,msg)
            footer=self.vars(a.get('footer') or '',phone,name,msg)
            payload={
                'Phone':route,
                'Body':body,
                'Title':title,
                'Footer':footer,
                'Buttons':buttons,
            }
            c,j=WUZ.call(token,'POST','/chat/send/buttons',payload,180)
            if c>=300 or (isinstance(j,dict) and j.get('success') is False):
                err=(j.get('error') if isinstance(j,dict) else str(j)) or str(j)
                raise RuntimeError(f'Error enviando menú guiado: HTTP {c} · {err}')
            guided_flow_set(pid,phone or str(route).split('@',1)[0],a)
            log(pid,'info',f'Menú guiado activado · {phone or route} · {a.get("flow_id") or "main"}')
            return

'''
if "if typ=='guided_menu':" not in s:
    anchor="        if typ=='human_handoff':\n"
    pos=s.find(anchor,s.find("def execute_action"))
    if pos<0:
        anchor="        if typ=='text':\n"
        pos=s.find(anchor,s.find("def execute_action"))
    if pos<0:
        raise SystemExit("No se encontró punto de acción para menú guiado")
    s=s[:pos]+guided_action+s[pos:]

# =========================================================
# WEBHOOK: active guided menu consumes invalid answers or maps valid buttons
# =========================================================
text_anchor="            m=d.get('Message') or d.get('message') or {}; text=(self.extract_text(m) or str(d.get('text') or root.get('message') or '')).strip()\n"
if "guided_menu_intercept(pid,token,route,phone,name,text)" not in s:
    if text_anchor not in s:
        raise SystemExit("No se encontró extracción de texto del webhook")
    s=s.replace(
        text_anchor,
        text_anchor+
        "            guided=self.guided_menu_intercept(pid,token,route,phone,name,text)\n"
        "            if guided is False:\n"
        "                return\n"
        "            if isinstance(guided,str) and guided:\n"
        "                text=guided\n",
        1
    )

# Templates accept guided_menu.
s=s.replace(
    "'location','contact','save_contact','human_handoff','buttons','list'",
    "'location','contact','save_contact','human_handoff','guided_menu','buttons','list'",
    1
)

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# =========================================================
# GUI: readable label + protect guided menu from accidental destructive editing
# =========================================================
g=gui_path.read_text(encoding="utf-8")

if "'guided_menu':'Menú guiado'" not in g:
    if "'human_handoff':'Pasar a asesor'," in g:
        g=g.replace(
            "'human_handoff':'Pasar a asesor',",
            "'human_handoff':'Pasar a asesor',\n    'guided_menu':'Menú guiado',",
            1
        )

# Summary in RuleDialog.
summary_anchor="""        if t=='human_handoff':
            return a.get('reason') or 'Pasar la conversación a un asesor'
"""
if "Menú guiado ·" not in g and summary_anchor in g:
    g=g.replace(
        summary_anchor,
        summary_anchor+
        "        if t=='guided_menu':\n"
        "            return f\"Menú guiado · {len(a.get('buttons') or [])} opciones · 1 aviso y luego espera silenciosa\"\n",
        1
    )

# Prevent ActionDialog from stripping menu metadata until a dedicated visual editor is added.
edit_anchor="""        i=int(selected[0])
        d=ActionDialog(self,self.actions[i])
"""
if "Este menú guiado forma parte del flujo protegido" not in g and edit_anchor in g:
    g=g.replace(
        edit_anchor,
        "        i=int(selected[0])\n"
        "        if self.actions[i].get('type')=='guided_menu':\n"
        "            messagebox.showinfo(\n"
        "                'Menú guiado',\n"
        "                'Este menú guiado forma parte del flujo protegido de la plantilla. '\n"
        "                'Puedes editar los textos de las otras acciones normalmente; el menú se conserva para evitar romper el control de respuestas.',\n"
        "                parent=self\n"
        "            )\n"
        "            return\n"
        "        d=ActionDialog(self,self.actions[i])\n",
        1
    )

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# =========================================================
# INSTALLER VERSION
# =========================================================
t=iss_path.read_text(encoding="utf-8")
if "2.2.4" not in t and "2.3.0" not in t:
    raise SystemExit("No se encontró versión 2.2.4 en installer.iss")
t=t.replace("2.2.4","2.3.0")
iss_path.write_text(t,encoding="utf-8")
