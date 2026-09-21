import ast
import pathlib
import sys

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))
import core_local as C

assert C.APP_VERSION=="2.3.3",C.APP_VERSION

main_path=root/"main_local.py"
src=main_path.read_text(encoding="utf-8")
ast.parse(src)

required=[
    "def acquire_or_recover_instance():",
    "def _find_existing_window():",
    "def _activate_window(hwnd):",
    "def _kill_stale_instances():",
    "def _startup_report(exc):",
    "MonopolioMultiBot-startup-error.txt",
    "ShowWindow(hwnd,9)",
    "taskkill','/F','/PID'",
    "No necesitas reinstalarlo",
    "def _stop_services(C):",
]
for phrase in required:
    assert phrase in src,phrase

# Regression: launcher must no longer silently exit merely because mutex exists.
assert "if not single_instance():" not in src
assert "def single_instance():" not in src

print("V2.3.3 TESTS OK: arranque autorrecuperable + recuperación de instancia oculta/trabada + diagnóstico visible")
