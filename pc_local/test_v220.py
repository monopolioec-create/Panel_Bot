import importlib.util
import pathlib
import sys
import tempfile
import time

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))

import core_local as C

# -------- versión --------
assert C.APP_VERSION=="2.2.0"

# -------- país/bandera --------
tests=[
    ("573001112233","🇨🇴","Colombia"),
    ("593991112233","🇪🇨","Ecuador"),
    ("5215512345678","🇲🇽","México"),
    ("34600111222","🇪🇸","España"),
    ("51999111222","🇵🇪","Perú"),
    ("12025550123","🇺🇸","Estados Unidos"),
]
for phone,flag,country in tests:
    info=C.detect_country_from_phone(phone)
    assert info["flag"]==flag,(phone,info)
    assert info["name"]==country,(phone,info)

eng=C.Engine()
rendered=eng.vars("@bandera @pais @telefono","573001112233","Ana","hola")
assert "🇨🇴 Colombia 573001112233" in rendered

# -------- guardar contacto con bandera --------
pid=C.add_profile("TEST V220 FLAGS")
C.google_status=lambda _pid:{"connected":False,"configured":False}
eng.execute_action(
    pid=pid,token="dummy",route="573001112233@s.whatsapp.net",
    phone="573001112233",name="Ana Cliente",msg="Hola",
    a={
        "type":"save_contact",
        "contact_name":"@nombre",
        "label":"Lead",
        "auto_country_flag":True
    },
    rule_name="Ingreso",started=time.perf_counter()
)
rows=C.contacts_for(pid)
assert len(rows)==1
assert rows[0]["name"]=="🇨🇴 Ana Cliente",rows[0]["name"]

# -------- modo asesor --------
assert not C.is_contact_paused(pid,"573001112233")
eng.execute_action(
    pid=pid,token="dummy",route="573001112233@s.whatsapp.net",
    phone="573001112233",name="Ana Cliente",msg="asesor",
    a={"type":"human_handoff","reason":"Compra lista"},
    rule_name="Asesor",started=time.perf_counter()
)
assert C.is_contact_paused(pid,"573001112233")
C.resume_contact(pid,"573001112233")
assert not C.is_contact_paused(pid,"573001112233")

# -------- días seleccionados --------
sid=C.save_schedule(pid,{
    "kind":"status_text",
    "run_date":"2026-09-21",
    "run_time":"18:30",
    "recurrence":"selected_days",
    "weekdays":"0,2,4",
    "text":"Estado de prueba",
    "active":True,
})
row=next(r for r in C.schedules_for(pid) if int(r["id"])==int(sid))
assert row["recurrence"]=="selected_days"
assert row["weekdays"]=="0,2,4"

# -------- plantilla acepta handoff y bandera --------
td=pathlib.Path(tempfile.mkdtemp(prefix="v220-template-"))
tpl=td/"flujo.mbtpl"
tpl.write_text("""{
  "format": "monopolio_multibot_template",
  "schema_version": 1,
  "template": {"name": "Flujo comercial"},
  "rules": [
    {
      "name": "Ingreso",
      "match_type": "exact",
      "pattern": "INICIO",
      "priority": 1,
      "actions": [
        {"type": "save_contact", "contact_name": "@nombre", "auto_country_flag": true},
        {"type": "human_handoff", "reason": "Solicitó asesor"}
      ]
    }
  ]
}""",encoding="utf-8")
res=C.import_rule_template(pid,tpl)
assert res["imported_count"]==1

# -------- GUI --------
gui_path=root/"gui_local.py"
gui=gui_path.read_text(encoding="utf-8")
compile(gui,str(gui_path),"exec")
assert "self.option_add('*Font','{Segoe UI} 10')" in gui
assert "self.option_add('*Font','Segoe UI 10')" not in gui
for phrase in [
    "Días seleccionados",
    "Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo",
    "Agregar bandera automática según el código del país",
    "Pasar a asesor",
    "Reactivar bot",
]:
    assert phrase in gui,phrase

spec=importlib.util.spec_from_file_location("gui_local_test_v220",gui_path)
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
for method in [
    "status_dialog","refresh_status",
    "pause_selected_contact","resume_selected_contact",
    "_paint_glow","refresh_google_contacts_status"
]:
    assert hasattr(G.App,method),method

print("V2.2.0 TESTS OK: font fix + selected weekdays + country flags + human handoff + templates")
