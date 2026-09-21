import importlib.util
import json
import pathlib
import sys
import time

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))
import core_local as C

assert C.APP_VERSION=="2.3.0",C.APP_VERSION

# Variable fallback.
eng=C.Engine()
assert eng.vars("Hola @nombre_cliente","573001112233","","hola")=="Hola Cliente"
assert eng.vars("Hola @nombre_cliente","573001112233","Ana","hola")=="Hola Ana"

pid=C.add_profile("TEST V230 GUIDED FLOW")
phone="573001112233"
route=phone+"@s.whatsapp.net"

menu={
    "type":"guided_menu",
    "flow_id":"mr_main",
    "title":"Monopolio Records",
    "text":"Selecciona una opción",
    "footer":"Atención guiada",
    "invalid_text":"Respuesta no válida. Selecciona una opción.",
    "max_invalid":1,
    "buttons":[
        {"id":"TRABAJOS","text":"Ver trabajos","aliases":["trabajos"]},
        {"id":"PRECIOS","text":"Ver precios","aliases":["precios"]},
        {"id":"ASESOR","text":"Hablar con asesor","aliases":["asesor"]},
    ],
}

calls=[]
class FakeW:
    @staticmethod
    def call(token,method,path,payload,timeout):
        calls.append((method,path,payload,timeout))
        return 200,{"success":True}
old_wuz=C.WUZ
C.WUZ=FakeW

# Arm menu via action.
eng.execute_action(
    pid,"tok",route,phone,"Ana","hola",
    menu,"Bienvenida",time.perf_counter()
)
st=C.guided_flow_get(pid,phone)
assert st and int(st["invalid_count"])==0,st
assert calls[-1][1]=="/chat/send/buttons"

# First invalid => warning + repeated menu.
calls.clear()
res=eng.guided_menu_intercept(pid,"tok",route,phone,"Ana","quiero llamar")
assert res is False
assert [x[1] for x in calls]==["/chat/send/text","/chat/send/buttons"],calls
st=C.guided_flow_get(pid,phone)
assert int(st["invalid_count"])==1,st

# Second invalid => silence.
calls.clear()
res=eng.guided_menu_intercept(pid,"tok",route,phone,"Ana","no, quiero hablar ya")
assert res is False
assert calls==[],calls
st=C.guided_flow_get(pid,phone)
assert int(st["invalid_count"])==1,st

# Valid choice after silence => flow resumes and state clears.
res=eng.guided_menu_intercept(pid,"tok",route,phone,"Ana","Ver precios")
assert res=="PRECIOS",res
assert C.guided_flow_get(pid,phone) is None

C.WUZ=old_wuz

# Template validator must accept guided_menu.
assert "guided_menu" in C.TEMPLATE_ACTION_TYPES,C.TEMPLATE_ACTION_TYPES

gui=(root/"gui_local.py").read_text(encoding="utf-8")
for phrase in [
    "Menú guiado",
    "1 aviso y luego espera silenciosa",
    "flujo protegido",
]:
    assert phrase in gui,phrase

spec=importlib.util.spec_from_file_location("gui_local_test_v230",root/"gui_local.py")
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

print("V2.3.0 TESTS OK: menú guiado + primer error con aviso + segundo error silencioso + reanudación al elegir opción válida")
