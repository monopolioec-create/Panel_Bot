import pathlib
import sys
import inspect

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
sys.path.insert(0,str(root))

import core_local as C
assert C.APP_VERSION=="2.3.1",C.APP_VERSION

src=(root/"core_local.py").read_text(encoding="utf-8")
assert "guided_token=self.prepare(pid)" in src
assert "guided=self.guided_menu_intercept(pid,guided_token,route,phone,name,text)" in src
assert "guided=self.guided_menu_intercept(pid,token,route,phone,name,text)" not in src

source=inspect.getsource(C.Engine.on_webhook)
assert "guided_token=self.prepare(pid)" in source
assert "guided_menu_intercept(pid,guided_token" in source

print("V2.3.1 TESTS OK: webhook token initialized before guided-menu interception")
