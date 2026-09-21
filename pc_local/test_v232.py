import pathlib
import sys
import time
from datetime import datetime

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))
import core_local as C

assert C.APP_VERSION=="2.3.2",C.APP_VERSION

pid=C.add_profile("TEST V232 AUTO RESUME")
phone="573001230987"

# 3-day handoff via the real action.
eng=C.Engine()
eng.execute_action(
    pid,"token",phone+"@s.whatsapp.net",phone,"Cliente","ASESOR",
    {
        "type":"human_handoff",
        "reason":"Prueba de pausa",
        "auto_resume_days":3,
        "delay_ms":0
    },
    "30 - Conversar con un asesor",
    time.perf_counter()
)

row=C.q(
    "SELECT * FROM paused_contacts WHERE profile_id=? AND phone=?",
    (pid,phone),
    one=True
)
assert row,row
assert row.get("resume_at"),row
delta=(datetime.fromisoformat(row["resume_at"])-datetime.now()).total_seconds()
assert 3*86400-20 <= delta <= 3*86400+20,delta
assert C.is_contact_paused(pid,phone) is True

# Expired pause is automatically removed on the next incoming-message check.
C.x(
    "UPDATE paused_contacts SET resume_at=? WHERE profile_id=? AND phone=?",
    ("2000-01-01T00:00:00",pid,phone)
)
assert C.is_contact_paused(pid,phone) is False
assert C.q(
    "SELECT * FROM paused_contacts WHERE profile_id=? AND phone=?",
    (pid,phone),
    one=True
) is None

gui=(root/"gui_local.py").read_text(encoding="utf-8")
for phrase in [
    "Reactivar automáticamente después de (días)",
    "auto_resume_days",
    "Reactiva en",
]:
    assert phrase in gui,phrase

print("V2.3.2 TESTS OK: handoff temporal + reactivación automática por días")
