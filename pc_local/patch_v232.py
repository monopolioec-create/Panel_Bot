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
if "APP_VERSION = '2.3.1'" not in s and "APP_VERSION = '2.3.2'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.3.1")
s=s.replace("APP_VERSION = '2.3.1'","APP_VERSION = '2.3.2'",1)

# =========================================================
# PAUSA CON VENCIMIENTO AUTOMÁTICO
# =========================================================
expiry_schema = r'''
def ensure_handoff_resume_column():
    with DB_LOCK, db() as con:
        cols={r['name'] for r in con.execute('PRAGMA table_info(paused_contacts)').fetchall()}
        if 'resume_at' not in cols:
            con.execute("ALTER TABLE paused_contacts ADD COLUMN resume_at TEXT NOT NULL DEFAULT ''")
        con.commit()

ensure_handoff_resume_column()
'''
expiry_schema=textwrap.dedent(expiry_schema)
if "def ensure_handoff_resume_column" not in s:
    anchor="ensure_handoff_table()\n"
    pos=s.find(anchor)
    if pos<0:
        raise SystemExit("No se encontró ensure_handoff_table()")
    pos+=len(anchor)
    s=s[:pos]+"\n"+expiry_schema+"\n"+s[pos:]

pause_fn = r'''
def pause_contact(profile_id,phone,reason='',auto_resume_hours=0):
    phone=normalize_contact_phone(phone)
    if not phone:
        raise RuntimeError('No se pudo identificar el número del cliente.')
    try:
        hours=max(0.0,float(auto_resume_hours or 0))
    except Exception:
        hours=0.0
    resume_at=''
    if hours>0:
        resume_at=datetime.fromtimestamp(time.time()+(hours*3600)).isoformat(timespec='seconds')
    x(
        'INSERT OR REPLACE INTO paused_contacts(profile_id,phone,paused_at,reason,resume_at) VALUES(?,?,?,?,?)',
        (
            profile_id,
            phone,
            datetime.now().isoformat(timespec='seconds'),
            str(reason or '')[:300],
            resume_at
        )
    )
'''
pause_fn=textwrap.dedent(pause_fn)
s,n=re.subn(
    r"def pause_contact\(profile_id,phone,reason=''\):.*?(?=\ndef resume_contact\(profile_id,phone\):)",
    lambda _m:pause_fn.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar pause_contact")

paused_fn = r'''
def is_contact_paused(profile_id,phone):
    phone=normalize_contact_phone(phone)
    if not phone:
        return False
    row=q(
        'SELECT profile_id,phone,resume_at FROM paused_contacts WHERE profile_id=? AND phone=?',
        (profile_id,phone),
        one=True
    )
    if not row:
        return False
    resume_at=str(row.get('resume_at') or '').strip()
    if resume_at:
        try:
            if datetime.now()>=datetime.fromisoformat(resume_at):
                x(
                    'DELETE FROM paused_contacts WHERE profile_id=? AND phone=?',
                    (profile_id,phone)
                )
                try:
                    log(profile_id,'info',f'Bot reactivado automáticamente · {phone}')
                except Exception:
                    pass
                return False
        except Exception:
            pass
    return True
'''
paused_fn=textwrap.dedent(paused_fn)
s,n=re.subn(
    r"def is_contact_paused\(profile_id,phone\):.*?(?=\n\S)",
    lambda _m:paused_fn.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar is_contact_paused")

# La acción de handoff toma días configurables y los convierte a horas.
old_action = """        if typ=='human_handoff':
            reason=self.vars(a.get('reason') or 'Cliente solicitó hablar con el equipo',phone,name,msg)
            pause_contact(pid,phone or str(route).split('@',1)[0],reason)
            log(pid,'info',f'Modo asesor activado · {phone or route}')
            return
"""
new_action = """        if typ=='human_handoff':
            reason=self.vars(a.get('reason') or 'Cliente solicitó hablar con el equipo',phone,name,msg)
            try:
                auto_days=max(0.0,float(a.get('auto_resume_days') or 0))
            except Exception:
                auto_days=0.0
            pause_contact(
                pid,
                phone or str(route).split('@',1)[0],
                reason,
                auto_resume_hours=auto_days*24
            )
            if auto_days>0:
                log(pid,'info',f'Modo asesor activado · reactivación automática en {auto_days:g} día(s) · {phone or route}')
            else:
                log(pid,'info',f'Modo asesor activado · {phone or route}')
            return
"""
if old_action not in s:
    raise SystemExit("No se encontró acción human_handoff actual")
s=s.replace(old_action,new_action,1)

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# =========================================================
# GUI: CAMPO EDITABLE DE DÍAS
# =========================================================
g=gui_path.read_text(encoding="utf-8")

old_ui = """            r=ttk.Frame(self.body);r.pack(fill='x',pady=5)
            ttk.Label(r,text='Motivo',width=25).pack(side='left')
            sv=tk.StringVar(value=self.v.get('reason','Cliente solicitó hablar con el equipo'))
            self.widgets['reason']=sv
            ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)
"""
new_ui = """            r=ttk.Frame(self.body);r.pack(fill='x',pady=5)
            ttk.Label(r,text='Motivo',width=25).pack(side='left')
            sv=tk.StringVar(value=self.v.get('reason','Cliente solicitó hablar con el equipo'))
            self.widgets['reason']=sv
            ttk.Entry(r,textvariable=sv).pack(side='left',fill='x',expand=True)

            r2=ttk.Frame(self.body);r2.pack(fill='x',pady=5)
            ttk.Label(r2,text='Reactivar automáticamente después de (días)',width=38).pack(side='left')
            auto_days=tk.StringVar(value=str(self.v.get('auto_resume_days',0)))
            self.widgets['auto_resume_days']=auto_days
            ttk.Entry(r2,textvariable=auto_days,width=10).pack(side='left')
            ttk.Label(
                self.body,
                text='Ejemplo: 3 = el bot queda en modo asesor durante 3 días. '
                     'Al cumplirse el plazo, el siguiente mensaje del cliente vuelve a activar las reglas automáticas. '
                     'Usa 0 para mantener la pausa manual indefinidamente.',
                wraplength=700,foreground=MUTED
            ).pack(anchor='w',pady=(2,8))
"""
if old_ui not in g:
    raise SystemExit("No se encontró UI de human_handoff")
g=g.replace(old_ui,new_ui,1)

# Resumen visible en la regla.
old_summary="""        if t=='human_handoff':
            return a.get('reason') or 'Pasar la conversación a un asesor'
"""
new_summary="""        if t=='human_handoff':
            reason=a.get('reason') or 'Pasar la conversación a un asesor'
            try:
                days=float(a.get('auto_resume_days') or 0)
            except Exception:
                days=0
            if days>0:
                return f"{reason} · Reactiva en {days:g} día(s)"
            return reason
"""
if old_summary not in g:
    raise SystemExit("No se encontró summary human_handoff")
g=g.replace(old_summary,new_summary,1)

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# =========================================================
# INSTALLER
# =========================================================
t=iss_path.read_text(encoding="utf-8")
if "2.3.1" not in t and "2.3.2" not in t:
    raise SystemExit("No se encontró versión 2.3.1 en installer.iss")
t=t.replace("2.3.1","2.3.2")
iss_path.write_text(t,encoding="utf-8")
