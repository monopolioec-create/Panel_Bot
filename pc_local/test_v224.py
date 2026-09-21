import ast
import importlib.util
import pathlib
import sys

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))

import core_local as C
assert C.APP_VERSION=="2.2.4",C.APP_VERSION

gui_path=root/"gui_local.py"
src=gui_path.read_text(encoding="utf-8")
tree=ast.parse(src)

app=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="App")
methods={n.name:n for n in app.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

for name in [
    "make_tabs","build_contacts","refresh_contacts",
    "refresh_google_contacts_status","connect_google_contacts",
    "disconnect_google_contacts","sync_all_google_contacts"
]:
    assert name in methods,name

make_src=ast.get_source_segment(src,methods["make_tabs"])
assert "'Contactos'" in make_src,make_src
assert "self.build_contacts()" in make_src,make_src
assert make_src.index("'Archivos'") < make_src.index("'Contactos'") < make_src.index("'Estados'"),make_src

profile_src=ast.get_source_segment(src,methods["profile_changed"])
assert "self.refresh_contacts()" in profile_src,profile_src
assert "self.refresh_google_contacts_status()" in profile_src,profile_src

for phrase in [
    "Cuenta Google destino",
    "Correo que recibirá los contactos:",
    "Seleccionar / cambiar cuenta",
    "Sincronizar pendientes",
    "Desconectar",
]:
    assert phrase in src,phrase

# Import the resulting module to catch runtime definition errors.
spec=importlib.util.spec_from_file_location("gui_local_test_v224",gui_path)
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
assert hasattr(G.App,"build_contacts")
assert hasattr(G.App,"connect_google_contacts")

print("V2.2.4 TESTS OK: pestaña Contactos visible entre Archivos y Estados + panel Google destino disponible")
