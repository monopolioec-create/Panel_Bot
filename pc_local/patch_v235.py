import pathlib
import re
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
gui_path=root/"gui_local.py"
iss_path=root/"installer.iss"

s=core_path.read_text(encoding="utf-8")

if "APP_VERSION = '2.3.4'" not in s and "APP_VERSION = '2.3.5'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.3.4")
s=s.replace("APP_VERSION = '2.3.4'","APP_VERSION = '2.3.5'",1)

silent_method = r'''
    def guided_menu_intercept(self,pid,token,route,phone,name,text):
        state_key=phone or route
        state=guided_flow_get(pid,state_key)
        if not state:
            return None

        try:
            action=json.loads(state.get('action_json') or '{}')
        except Exception:
            guided_flow_clear(pid,state_key)
            return None

        buttons=action.get('buttons') or []
        choice=guided_option_match(text,buttons)
        if choice:
            guided_flow_clear(pid,state_key)
            selected=str(choice.get('id') or choice.get('text') or '').strip()
            log(pid,'info',f'Opción válida de menú guiado · {state_key} · {selected}')
            return selected

        # Cualquier texto que no sea una opción válida se ignora en silencio.
        # No se manda advertencia, no se repite el menú y el estado queda
        # pendiente hasta que el cliente pulse una de las opciones originales.
        log(pid,'info',f'Respuesta fuera del menú ignorada · esperando opción válida · {state_key}')
        return False
'''
silent_method=textwrap.indent(textwrap.dedent(silent_method).strip()+"\n","    ")

s,n=re.subn(
    r"    def guided_menu_intercept\(self,pid,token,route,phone,name,text\):.*?(?=\n    def execute_action\(self,pid,token,route,phone,name,msg,a,rule_name,started\):)",
    lambda _m:silent_method.rstrip()+"\n",
    s,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar guided_menu_intercept")

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

g=gui_path.read_text(encoding="utf-8")
g=g.replace(
    'return f"Menú guiado · {len(a.get(\'buttons\') or [])} opciones · 1 aviso y luego espera silenciosa"',
    'return f"Menú guiado · {len(a.get(\'buttons\') or [])} opciones · espera silenciosa hasta elegir una opción"',
    1
)
compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

t=iss_path.read_text(encoding="utf-8")
if "2.3.4" not in t and "2.3.5" not in t:
    raise SystemExit("No se encontró versión 2.3.4 en installer.iss")
t=t.replace("2.3.4","2.3.5")
iss_path.write_text(t,encoding="utf-8")
