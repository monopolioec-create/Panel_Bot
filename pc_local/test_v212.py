import importlib.util
import pathlib
import sys

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
gui_path=root/"gui_local.py"
core_path=root/"core_local.py"

gui=gui_path.read_text(encoding="utf-8")
core=core_path.read_text(encoding="utf-8")

assert "APP_VERSION = '2.1.2'" in core
compile(gui,str(gui_path),"exec")

required=[
    "BG='#070B12'",
    "CARD='#0F1722'",
    "GOLD='#D6A842'",
    "GREEN='#39FF88'",
    "CYAN='#4FD7FF'",
    "def _paint_glow",
    "def _set_status",
    "def _set_whatsapp_status",
    "VINCULADO",
    "ENCENDIDO",
    "PENDIENTE",
    "Accent.TButton",
    "TNotebook.Tab",
    "Treeview.Heading",
]
for item in required:
    assert item in gui, f"Falta elemento visual v2.1.2: {item}"

# Importar la GUI y comprobar que los métodos esenciales siguen presentes.
spec=importlib.util.spec_from_file_location("gui_local_test_v212",gui_path)
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

for method in [
    "refresh_google_contacts_status",
    "connect_google_contacts",
    "build_contacts",
    "build_media",
    "build_status",
    "import_rule_template",
    "_paint_glow",
    "_set_status",
    "_set_whatsapp_status",
]:
    assert hasattr(G.App,method), f"Falta método después del rediseño: {method}"

print("V2.1.2 VISUAL TESTS OK: dark futuristic theme + glow indicators + previous modules preserved")
