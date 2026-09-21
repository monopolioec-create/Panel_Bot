import pathlib
import sys
import time

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))
import core_local as C

assert C.APP_VERSION=="2.3.5",C.APP_VERSION

pid=C.add_profile("TEST V235 SILENT MENU")
phone="573001112233"
route=phone+"@s.whatsapp.net"

menu={
    "type":"guided_menu",
    "flow_id":"mr-main",
    "title":"MONOPOLIO RECORDS",
    "text":"¿Qué deseas hacer ahora?",
    "invalid_text":"ESTE TEXTO NO DEBE ENVIARSE",
    "max_invalid":99,
    "buttons":[
        {"id":"TRABAJOS","text":"Ver nuestros trabajos"},
        {"id":"PRECIOS","text":"Ver precios"},
        {"id":"ASESOR","text":"Conversar con un asesor"},
    ],
}

calls=[]
class FakeW:
    @staticmethod
    def call(token,method,path,payload,timeout):
        calls.append((path,payload))
        return 200,{"success":True}
old=C.WUZ
C.WUZ=FakeW

eng=C.Engine()
eng.execute_action(
    pid,"tok",route,phone,"Cliente","hola",
    menu,"Bienvenida",time.perf_counter()
)
assert calls and calls[-1][0]=="/chat/send/buttons"
assert C.guided_flow_get(pid,phone)

# Respuesta fuera del menú: cero mensajes adicionales y estado sigue pendiente.
calls.clear()
res=eng.guided_menu_intercept(pid,"tok",route,phone,"Cliente","disculpe")
assert res is False
assert calls==[],calls
assert C.guided_flow_get(pid,phone)

# Otra respuesta fuera del menú: sigue sin responder ni repetir menú.
res=eng.guided_menu_intercept(pid,"tok",route,phone,"Cliente","quiero otra cosa")
assert res is False
assert calls==[],calls
assert C.guided_flow_get(pid,phone)

# Al pulsar una opción válida, continúa el flujo.
res=eng.guided_menu_intercept(pid,"tok",route,phone,"Cliente","Ver precios")
assert res=="PRECIOS",res
assert C.guided_flow_get(pid,phone) is None

C.WUZ=old

src=(root/"core_local.py").read_text(encoding="utf-8")
assert "Respuesta fuera del menú ignorada" in src
assert "No se manda advertencia" in src

gui=(root/"gui_local.py").read_text(encoding="utf-8")
assert "espera silenciosa hasta elegir una opción" in gui

print("V2.3.5 TESTS OK: menú llega una vez + respuestas libres ignoradas + espera hasta opción válida")
