import importlib.util
import pathlib
import sys

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))

import core_local as C

assert C.APP_VERSION=="2.1.3"

# Persistence for selected weekdays.
pid=C.add_profile("TEST DIAS V213")
sid=C.save_schedule(pid,{
    "kind":"status_text",
    "run_date":"2026-09-20",
    "run_time":"16:30",
    "recurrence":"weekdays",
    "weekdays":"0,2,4",
    "text":"Prueba lunes miércoles viernes",
    "active":True,
})
row=next(x for x in C.schedules_for(pid) if int(x["id"])==int(sid))
assert row["recurrence"]=="weekdays"
assert row["weekdays"]=="0,2,4"

gui_path=root/"gui_local.py"
gui=gui_path.read_text(encoding="utf-8")
compile(gui,str(gui_path),"exec")
assert "self.option_add('*Font','{Segoe UI} 10')" in gui
assert "Días seleccionados" in gui
for day in ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]:
    assert day in gui

spec=importlib.util.spec_from_file_location("gui_local_v213",gui_path)
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

# Real Tk smoke-test: this catches invalid font specifications such as "Segoe UI 10".
G.C.WUZ.start=lambda:None
G.C.ENGINE.prepare=lambda pid:"dummy"
G.C.WUZ.flags=lambda token:(False,False,None)
G.App.start_tray=lambda self:None

app=G.App()
app.withdraw()
app.update_idletasks()
assert hasattr(app,"home_engine")
assert hasattr(app,"wa_glow")
assert hasattr(app,"status_tree")
app.destroy()

print("V2.1.3 UI SMOKE OK: tema oscuro inicia + Segoe UI corregida + días seleccionados persistentes")
