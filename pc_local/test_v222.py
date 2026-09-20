import importlib.util
import pathlib
import sys

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))

import core_local as C
assert C.APP_VERSION=="2.2.2", C.APP_VERSION

gui_path=root/"gui_local.py"
gui=gui_path.read_text(encoding="utf-8")

required=[
    "side='bottom'",
    "GUARDAR REGLA",
    "Tamaño:",
    "media_thumb_size",
    "def _video_thumbnail_path",
    "imageio_ffmpeg",
    "♫",
    "'PDF'",
    "show='tree headings'",
    "Status.Treeview",
    "self.status_photo_refs",
    "image=photo if photo else ''",
]
for phrase in required:
    assert phrase in gui, phrase

spec=importlib.util.spec_from_file_location("gui_local_test_v222",gui_path)
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

for method in [
    "build_media","refresh_media_gallery","_video_thumbnail_path","_media_photo",
    "_on_media_thumb_size","_media_thumb_wheel",
    "build_status","refresh_status"
]:
    assert hasattr(G.App,method),method

import imageio_ffmpeg
ffmpeg=pathlib.Path(imageio_ffmpeg.get_ffmpeg_exe())
assert ffmpeg.exists(), ffmpeg

req=(root/"requirements.txt").read_text(encoding="utf-8").lower()
assert "imageio-ffmpeg" in req

print("V2.2.2 TESTS OK: footer fijo + miniaturas de video/imagen + iconos + tamaño ajustable + previews de estados")
