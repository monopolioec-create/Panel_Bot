import pathlib
import sys
import time

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))
import core_local as C

assert C.APP_VERSION=="2.3.4",C.APP_VERSION

eng=C.Engine()
pid=C.add_profile("TEST V234 USERNAME LID")
route="179001234567890@lid"

# Standard phone identity remains unchanged.
assert C.conversation_key("573001234567@s.whatsapp.net")=="573001234567"
# LID/username-style identifiers remain addressable and are not converted to phone numbers.
assert C.conversation_key(route)==route
assert C.conversation_key("vicotenoriox@lid")=="vicotenoriox@lid"

# Save-contact with no public phone must NOT abort the rule.
calls=[]
class FakeW:
    @staticmethod
    def call(token,method,path,payload,timeout):
        calls.append((path,payload))
        return 200,{"success":True}
old_wuz=C.WUZ
C.WUZ=FakeW

eng.execute_action(
    pid,"tok",route,"","@vicotenoriox","hola",
    {"type":"save_contact","contact_name":"@nombre","label":"Cliente"},
    "Bienvenida",time.perf_counter()
)
# The following action can still reply to the exact incoming route.
eng.execute_action(
    pid,"tok",route,"","@vicotenoriox","hola",
    {"type":"text","text":"Hola @nombre"},
    "Bienvenida",time.perf_counter()
)
assert calls and calls[-1][0]=="/chat/send/text",calls
assert calls[-1][1]["Phone"]==route,calls
assert calls[-1][1]["Body"]=="Hola @vicotenoriox",calls

# Guided menu must work without a phone number.
menu={
    "type":"guided_menu",
    "flow_id":"username-flow",
    "text":"Escoge",
    "buttons":[
        {"id":"PRECIOS","text":"Ver precios"},
        {"id":"ASESOR","text":"Hablar con asesor"},
    ],
    "invalid_text":"Opción inválida",
    "max_invalid":1,
}
eng.execute_action(
    pid,"tok",route,"","@vicotenoriox","hola",
    menu,"Bienvenida",time.perf_counter()
)
assert C.guided_flow_get(pid,route), "El estado guiado debe guardarse por JID si no hay teléfono"
choice=eng.guided_menu_intercept(pid,"tok",route,"","@vicotenoriox","Ver precios")
assert choice=="PRECIOS",choice
assert C.guided_flow_get(pid,route) is None

# Advisor handoff must also work for username/LID chats.
eng.execute_action(
    pid,"tok",route,"","@vicotenoriox","ASESOR",
    {"type":"human_handoff","reason":"Asesor","auto_resume_days":3},
    "Asesor",time.perf_counter()
)
assert C.is_contact_paused(pid,route) is True
C.resume_contact(pid,route)
assert C.is_contact_paused(pid,route) is False

C.WUZ=old_wuz

src=(root/"core_local.py").read_text(encoding="utf-8")
assert "Cliente identificado por usuario/LID sin número visible" in src
assert "is_contact_paused(pid,phone or route)" in src

print("V2.3.4 TESTS OK: usuarios/LID responden sin número + save_contact no bloquea + menú guiado + asesor")
