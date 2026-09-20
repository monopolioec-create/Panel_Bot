import importlib.util
import pathlib
import sys
import tempfile

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))

import core_local as C

# ---------------------------------------------------------------------------
# WhatsApp Status payload tests
# ---------------------------------------------------------------------------
captured=[]
def fake_call(token,method,path,body=None,timeout=60):
    captured.append((token,method,path,body,timeout))
    return 200,{"success":True,"data":{"Details":"Sent"}}

C.WUZ.call=fake_call
C.ENGINE.prepare=lambda pid:"token-test"
C.get_profile=lambda pid:{"id":pid,"name":"Prueba"}

td=pathlib.Path(tempfile.mkdtemp(prefix="multibot-status-test-"))
img=td/"estado.png"
img.write_bytes(b"\x89PNG\r\n\x1a\n"+b"0"*64)
vid=td/"estado.mp4"
vid.write_bytes(b"\x00\x00\x00\x18ftypmp42"+b"0"*64)

img_id=C.add_media(str(img))
vid_id=C.add_media(str(vid))

C.publish_whatsapp_status("p1","status_text","Hola Colombia",0)
assert captured[-1][2]=="/chat/send/text"
assert captured[-1][3]["Phone"]=="status@broadcast"
assert captured[-1][3]["Body"]=="Hola Colombia"

C.publish_whatsapp_status("p1","status_image","Pie imagen",img_id)
assert captured[-1][2]=="/chat/send/image"
assert captured[-1][3]["Phone"]=="status@broadcast"
assert captured[-1][3]["Caption"]=="Pie imagen"
assert captured[-1][3]["Image"].startswith("data:image/png;base64,")

C.publish_whatsapp_status("p1","status_video","Pie video",vid_id)
assert captured[-1][2]=="/chat/send/video"
assert captured[-1][3]["Phone"]=="status@broadcast"
assert captured[-1][3]["Caption"]=="Pie video"
assert captured[-1][3]["Video"].startswith("data:video/mp4;base64,")

# ---------------------------------------------------------------------------
# Schedule persistence tests
# ---------------------------------------------------------------------------
pid=C.add_profile("TEST ESTADOS V210")
sid=C.save_schedule(pid,{
    "kind":"status_image",
    "run_date":"2026-09-21",
    "run_time":"14:45",
    "recurrence":"daily",
    "text":"Hola",
    "media_id":img_id,
    "active":True,
})
row=next(x for x in C.schedules_for(pid) if int(x["id"])==int(sid))
assert row["kind"]=="status_image"
assert row["recurrence"]=="daily"
assert int(row["media_id"])==img_id

# ---------------------------------------------------------------------------
# GUI source localization and feature checks
# ---------------------------------------------------------------------------
gui=(root/"gui_local.py").read_text(encoding="utf-8")
compile(gui,str(root/"gui_local.py"),"exec")

bad_sequences=["automÃ","Ã¡","Ã©","Ã­","Ã³","Ãº","Ã±","Â¿","Â¡"]
for bad in bad_sequences:
    assert bad not in gui, f"Texto con codificación dañada: {bad}"

required=[
    "Reglas automáticas",
    "Una sola vez",
    "Todos los días",
    "Miniaturas",
    "Estados de WhatsApp programados",
    "Publicar ahora",
    "Guardar cliente",
    "Cualquier mensaje",
    "Empieza por",
    "Esperar antes de enviar (segundos)",
]
for phrase in required:
    assert phrase in gui, f"Falta texto localizado: {phrase}"

for forbidden in [
    "text='Texto / caption'",
    "text='Retraso ms'",
    "values=['once','daily']",
    "text='Desconectar socket'",
]:
    assert forbidden not in gui, f"Quedó texto técnico visible: {forbidden}"

print("V2.1.0 TESTS OK: español Colombia + miniaturas/lista + fecha/hora interactiva + Estados texto/imagen/video")
