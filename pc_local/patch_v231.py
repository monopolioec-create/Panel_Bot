import pathlib
import sys

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
iss_path=root/"installer.iss"

s=core_path.read_text(encoding="utf-8")

if "APP_VERSION = '2.3.0'" not in s and "APP_VERSION = '2.3.1'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.3.0")
s=s.replace("APP_VERSION = '2.3.0'","APP_VERSION = '2.3.1'",1)

# v2.3.0 regression:
# guided_menu_intercept was injected immediately after extracting incoming text,
# but the original webhook creates the session token later. That made every
# incoming message fail before rules could run.
old="""            guided=self.guided_menu_intercept(pid,token,route,phone,name,text)
            if guided is False:
                return
            if isinstance(guided,str) and guided:
                text=guided
"""
new="""            guided_token=self.prepare(pid)
            guided=self.guided_menu_intercept(pid,guided_token,route,phone,name,text)
            if guided is False:
                return
            if isinstance(guided,str) and guided:
                text=guided
"""
if old not in s:
    raise SystemExit("No se encontró el bloque defectuoso de guided_menu_intercept")
s=s.replace(old,new,1)

compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

t=iss_path.read_text(encoding="utf-8")
if "2.3.0" not in t and "2.3.1" not in t:
    raise SystemExit("No se encontró versión 2.3.0 en installer.iss")
t=t.replace("2.3.0","2.3.1")
iss_path.write_text(t,encoding="utf-8")
