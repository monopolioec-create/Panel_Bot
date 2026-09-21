import ast
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
if "APP_VERSION = '2.2.3'" not in s and "APP_VERSION = '2.2.4'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.2.3")
s=s.replace("APP_VERSION = '2.2.3'","APP_VERSION = '2.2.4'")
compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# =========================================================
# GUI: force Contactos tab into the real main navigation
# =========================================================
g=gui_path.read_text(encoding="utf-8")

new_make_tabs = r'''
    def make_tabs(self):
        self.tabs={}
        for name in [
            'Inicio','Negocios','WhatsApp','Reglas','Archivos',
            'Contactos',
            'Estados','Logs','Configuración'
        ]:
            f=ttk.Frame(self.nb,padding=16)
            self.nb.add(f,text=name)
            self.tabs[name]=f

        self.build_home()
        self.build_profiles()
        self.build_whatsapp()
        self.build_rules()
        self.build_media()
        self.build_contacts()
        self.build_status()
        self.build_logs()
        self.build_settings()
'''
new_make_tabs=textwrap.indent(textwrap.dedent(new_make_tabs).strip()+"\n","    ")
g,n=re.subn(
    r"    def make_tabs\(self\):.*?(?=\n    def [A-Za-z_])",
    lambda _m:new_make_tabs.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar App.make_tabs")

# Ensure changing business refreshes both local contacts and visible Google destination.
profile_changed = r'''
    def profile_changed(self):
        self.refresh_home()
        self.refresh_rules()
        self.refresh_contacts()
        self.refresh_google_contacts_status()
        self.refresh_status()
        self.refresh_logs()
        self.refresh_whatsapp()
'''
profile_changed=textwrap.indent(textwrap.dedent(profile_changed).strip()+"\n","    ")
g,n=re.subn(
    r"    def profile_changed\(self\):.*?(?=\n    def [A-Za-z_])",
    lambda _m:profile_changed.rstrip(),
    g,count=1,flags=re.S
)
if n!=1:
    raise SystemExit("No se pudo reemplazar App.profile_changed")

# Fail the patch if the underlying Contacts/Google panel isn't present.
for required in [
    "    def build_contacts(self):",
    "    def refresh_contacts(self):",
    "    def refresh_google_contacts_status(self):",
    "Cuenta Google destino",
    "Correo que recibirá los contactos:",
    "Seleccionar / cambiar cuenta",
]:
    if required not in g:
        raise SystemExit(f"Falta componente requerido de Contactos/Google: {required}")

compile(g,str(gui_path),"exec")
gui_path.write_text(g,encoding="utf-8")

# =========================================================
# INSTALLER
# =========================================================
t=iss_path.read_text(encoding="utf-8")
if "2.2.3" not in t and "2.2.4" not in t:
    raise SystemExit("No se encontró versión 2.2.3 en installer.iss")
t=t.replace("2.2.3","2.2.4")
iss_path.write_text(t,encoding="utf-8")
