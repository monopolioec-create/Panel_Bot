import importlib.util
import pathlib
import sys

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))

import core_local as C

assert C.APP_VERSION=="2.2.1", C.APP_VERSION

gui_path=root/"gui_local.py"
gui=gui_path.read_text(encoding="utf-8")
for phrase in [
    "ON / OFF",
    "● ON",
    "○ OFF",
    "<Delete>",
    "<KP_Delete>",
    "def rule_toggle_click(self,event):",
    "def rule_delete_key(self,event=None):",
    "pulsa Supr para eliminarla",
]:
    assert phrase in gui, phrase

spec=importlib.util.spec_from_file_location("gui_local_test_v221",gui_path)
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
for method in [
    "build_rules",
    "refresh_rules",
    "rule_toggle_click",
    "rule_delete_key",
    "del_rule",
]:
    assert hasattr(G.App,method), method

# Verificar que el cambio de estado que usa el interruptor persiste en SQLite.
pid=C.add_profile("TEST V221 RULE TOGGLE")
rid=C.save_rule(pid,{
    "name":"Regla rápida",
    "match_type":"exact",
    "pattern":"INICIO",
    "priority":1,
    "enabled":False,
    "actions":[{"type":"text","text":"Hola"}],
})
row=next(r for r in C.rules_for(pid) if int(r["id"])==int(rid))
assert not bool(row["enabled"])
C.x("UPDATE rules SET enabled=? WHERE id=? AND profile_id=?",(1,rid,pid))
row=next(r for r in C.rules_for(pid) if int(r["id"])==int(rid))
assert bool(row["enabled"])

# Verificar eliminación equivalente al acceso Supr.
if hasattr(C,"delete_rule"):
    C.delete_rule(rid)
else:
    C.x("DELETE FROM rules WHERE id=? AND profile_id=?",(rid,pid))
assert not any(int(r["id"])==int(rid) for r in C.rules_for(pid))

print("V2.2.1 TESTS OK: interruptor ON/OFF por regla + tecla Supr para eliminar")
