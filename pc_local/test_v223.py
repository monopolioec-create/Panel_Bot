import json
import pathlib
import sys
import tempfile
import time

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))
import core_local as C

assert C.APP_VERSION=="2.2.3", C.APP_VERSION

# -------- WhatsApp PN vs LID resolution --------
eng=C.Engine()
pn="573228386498"
lid="123456789012345"
assert eng.phone(f"{lid}@lid",f"{pn}@s.whatsapp.net",f"{pn}@s.whatsapp.net")==pn
assert eng.phone(f"{pn}@s.whatsapp.net",f"{lid}@lid",f"{lid}@lid")==pn
assert eng.phone("",f"{pn}:14@s.whatsapp.net","")==pn
assert eng.phone(f"{lid}@lid",f"{lid}@lid",f"{lid}@lid")==''

pid=C.add_profile("TEST V223 CONTACT CAPTURE")
C.google_status=lambda _pid:{"connected":False,"configured":False,"email":""}
eng.execute_action(
    pid=pid,token="dummy",route=f"{pn}@s.whatsapp.net",
    phone=pn,name="SERFICAMBIOS",msg="hola",
    a={"type":"save_contact","contact_name":"@nombre","label":"Cliente"},
    rule_name="Bienvenida",started=time.perf_counter()
)
rows=C.contacts_for(pid)
assert any(r["phone"]==pn for r in rows),rows

# -------- Google selected destination email --------
# Restore real google_status after previous monkeypatch by reloading module.
import importlib
C=importlib.reload(C)
pid=C.add_profile("TEST V223 GOOGLE ACCOUNT")

td=pathlib.Path(tempfile.mkdtemp(prefix="v223-google-"))
cred=td/"credentials.json"
cred.write_text(json.dumps({"installed":{"client_id":"x","client_secret":"y","auth_uri":"https://example.com","token_uri":"https://example.com"}}),encoding="utf-8")

class FakeCreds:
    expired=False
    refresh_token="refresh"
    valid=True
    id_token={"email":"destino.prueba@gmail.com"}
    def to_json(self):
        return json.dumps({"token":"fake","refresh_token":"refresh","client_id":"x","client_secret":"y","token_uri":"https://example.com","scopes":C.GOOGLE_SCOPES})

class FakeFlow:
    def run_local_server(self,**kwargs):
        assert "select_account" in kwargs.get("prompt","")
        return FakeCreds()

class FakeInstalled:
    @staticmethod
    def from_client_secrets_file(path,scopes):
        assert pathlib.Path(path).exists()
        assert "openid" in scopes
        return FakeFlow()

C.InstalledAppFlow=FakeInstalled
result=C.google_connect(pid,str(cred))
assert result["email"]=="destino.prueba@gmail.com",result
st=C.google_status(pid)
assert st["connected"] is True,st
assert st["email"]=="destino.prueba@gmail.com",st

# Switching account must invalidate Google resource IDs from previous destination.
cid,_=C.save_customer_contact(pid,"573001234567","Cliente Uno","Cliente","","hola","Regla")
C.x("UPDATE contacts SET google_resource=?,google_account=?,google_synced_at=? WHERE id=?",("people/old","anterior@gmail.com","2026-01-01",cid))

class FakeCreds2(FakeCreds):
    id_token={"email":"nuevo.destino@gmail.com"}

class FakeFlow2:
    def run_local_server(self,**kwargs):
        return FakeCreds2()

class FakeInstalled2:
    @staticmethod
    def from_client_secrets_file(path,scopes):
        return FakeFlow2()

C.InstalledAppFlow=FakeInstalled2
C.google_connect(pid,None)
row=C.get_contact(cid)
assert row["google_resource"]=="",row
assert row["google_account"]=="",row
assert C.google_status(pid)["email"]=="nuevo.destino@gmail.com"

gui=(root/"gui_local.py").read_text(encoding="utf-8")
for phrase in [
    "Cuenta Google destino",
    "Correo que recibirá los contactos:",
    "Seleccionar / cambiar cuenta",
    "SINCRONIZACIÓN AUTOMÁTICA ACTIVA",
    "✓ Sincronizado",
    "⚠ Error",
    "identificadores internos LID",
]:
    assert phrase in gui,phrase

print("V2.2.3 TESTS OK: PN real vs LID + guardado local + selección explícita de correo Google destino")
