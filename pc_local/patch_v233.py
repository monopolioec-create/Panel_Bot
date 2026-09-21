import pathlib
import sys
import textwrap

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else r"pc_local\buildsrc")
core_path=root/"core_local.py"
main_path=root/"main_local.py"
iss_path=root/"installer.iss"

# Version
s=core_path.read_text(encoding="utf-8")
if "APP_VERSION = '2.3.2'" not in s and "APP_VERSION = '2.3.3'" not in s:
    raise SystemExit("No se encontró APP_VERSION 2.3.2")
s=s.replace("APP_VERSION = '2.3.2'","APP_VERSION = '2.3.3'",1)
compile(s,str(core_path),"exec")
core_path.write_text(s,encoding="utf-8")

# Robust autonomous launcher:
# - Do not silently quit when another process holds the mutex.
# - Restore a healthy existing window.
# - Kill a stale/hung invisible copy and recover automatically.
# - Show a visible startup error instead of failing silently.
# - Stop local services cleanly when the UI closes.
main = r'''
import bootstrap_imports
import csv
import ctypes
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback

MUTEX_NAME='MonopolioMultiBotDesktop_v2_Mutex'
_mutex=None


def _resource(name):
    base=getattr(sys,'_MEIPASS',os.path.dirname(os.path.abspath(sys.argv[0])))
    return os.path.join(base,name)


def _load_module(name):
    path=_resource(name+'.py')
    if not os.path.exists(path):
        raise RuntimeError('Falta el componente interno '+name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError('No se pudo cargar el componente interno '+name)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def _startup_report(exc):
    report=os.path.join(tempfile.gettempdir(),'MonopolioMultiBot-startup-error.txt')
    try:
        with open(report,'w',encoding='utf-8') as fh:
            fh.write('Monopolio MultiBot - Error de inicio\n')
            fh.write('='*60+'\n')
            fh.write(str(exc)+'\n\n')
            traceback.print_exc(file=fh)
    except Exception:
        pass
    return report


def _native_alert(title,message):
    try:
        if os.name=='nt':
            ctypes.windll.user32.MessageBoxW(None,str(message),str(title),0x10)
            return
    except Exception:
        pass
    try:
        from tkinter import Tk, messagebox
        root=Tk();root.withdraw()
        messagebox.showerror(title,message,parent=root)
        root.destroy()
    except Exception:
        pass


def _self_test():
    _load_module('core_local')
    _load_module('gui_local')
    return 0


def _find_existing_window():
    if os.name!='nt':
        return 0
    try:
        user32=ctypes.windll.user32
        matches=[]

        CALLBACK=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)

        def enum_proc(hwnd,lparam):
            try:
                length=user32.GetWindowTextLengthW(hwnd)
                if length<=0:
                    return True
                buf=ctypes.create_unicode_buffer(length+1)
                user32.GetWindowTextW(hwnd,buf,length+1)
                title=(buf.value or '').upper()
                if 'MONOPOLIO MULTIBOT' in title:
                    matches.append(int(hwnd))
            except Exception:
                pass
            return True

        user32.EnumWindows(CALLBACK(enum_proc),0)
        for hwnd in matches:
            try:
                # If the window is hung, don't reuse it; the launcher will recover.
                if hasattr(user32,'IsHungAppWindow') and user32.IsHungAppWindow(hwnd):
                    continue
                return hwnd
            except Exception:
                return hwnd
    except Exception:
        pass
    return 0


def _activate_window(hwnd):
    if not hwnd or os.name!='nt':
        return False
    try:
        user32=ctypes.windll.user32
        user32.ShowWindow(hwnd,9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def _other_same_exe_pids():
    if os.name!='nt' or not getattr(sys,'frozen',False):
        return []
    image=os.path.basename(sys.executable)
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    try:
        result=subprocess.run(
            ['tasklist','/FI',f'IMAGENAME eq {image}','/FO','CSV','/NH'],
            capture_output=True,text=True,errors='ignore',
            creationflags=flags,timeout=8
        )
        current=os.getpid()
        pids=[]
        for row in csv.reader((result.stdout or '').splitlines()):
            if len(row)<2:
                continue
            try:
                pid=int(str(row[1]).replace(',','').strip())
            except Exception:
                continue
            if pid!=current:
                pids.append(pid)
        return sorted(set(pids))
    except Exception:
        return []


def _kill_stale_instances():
    if os.name!='nt':
        return 0
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    killed=0
    for pid in _other_same_exe_pids():
        try:
            subprocess.run(
                ['taskkill','/F','/PID',str(pid)],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=flags,timeout=8
            )
            killed+=1
        except Exception:
            pass
    if killed:
        time.sleep(1.0)
    return killed


def _release_mutex():
    global _mutex
    if _mutex and os.name=='nt':
        try:
            ctypes.windll.kernel32.ReleaseMutex(_mutex)
        except Exception:
            pass
        try:
            ctypes.windll.kernel32.CloseHandle(_mutex)
        except Exception:
            pass
    _mutex=None


def _create_mutex():
    global _mutex
    if os.name!='nt':
        return True
    kernel32=ctypes.windll.kernel32
    _mutex=kernel32.CreateMutexW(None,False,MUTEX_NAME)
    return kernel32.GetLastError()!=183


def acquire_or_recover_instance():
    # First launch: acquire normally.
    if _create_mutex():
        return True

    # Another copy exists. If it has a healthy UI, bring it to the front.
    hwnd=_find_existing_window()
    if hwnd and _activate_window(hwnd):
        _release_mutex()
        return False

    # Existing process has no usable window or is hung. This is the condition
    # that previously forced a reinstall. Recover automatically.
    _release_mutex()
    _kill_stale_instances()

    # Give Windows a moment to release the old named mutex.
    for _ in range(12):
        if _create_mutex():
            return True
        hwnd=_find_existing_window()
        if hwnd and _activate_window(hwnd):
            _release_mutex()
            return False
        _release_mutex()
        time.sleep(0.25)

    _native_alert(
        'Monopolio MultiBot',
        'No se pudo recuperar una instancia anterior del programa.\n\n'
        'Espera unos segundos y vuelve a abrirlo. Ya no es necesario reinstalar.'
    )
    return False


def _stop_services(C):
    try:
        if hasattr(C,'ENGINE'):
            try:
                C.ENGINE.running=False
            except Exception:
                pass
        if hasattr(C,'WUZ') and hasattr(C.WUZ,'stop'):
            try:
                C.WUZ.stop()
            except Exception:
                pass
    except Exception:
        pass


def run_app():
    if '--self-test' in sys.argv:
        return _self_test()

    if not acquire_or_recover_instance():
        return 0

    C=None
    try:
        C=_load_module('core_local')
        G=_load_module('gui_local')

        app=G.App()

        def start_services():
            try:
                C.start_services()
                C.log('','info','Motor local iniciado correctamente')
            except Exception as e:
                try:
                    C.log('','error',f'No se pudo iniciar el motor: {e}')
                except Exception:
                    pass
                try:
                    from tkinter import messagebox
                    app.after(
                        0,
                        lambda:messagebox.showerror(
                            C.APP_NAME,
                            f'No se pudo iniciar el motor de WhatsApp:\n\n{e}',
                            parent=app
                        )
                    )
                except Exception:
                    pass

        threading.Thread(
            target=start_services,
            daemon=True,
            name='services'
        ).start()

        if '--background' in sys.argv:
            app.withdraw()

        app.mainloop()
        return 0

    except Exception as exc:
        report=_startup_report(exc)
        _native_alert(
            'Monopolio MultiBot - Error de inicio',
            'El programa encontró un problema al iniciar.\n\n'
            'No necesitas reinstalarlo. Se creó un diagnóstico en:\n'
            +report+
            '\n\nPuedes volver a abrir el programa después de cerrar este mensaje.'
        )
        return 2
    finally:
        if C is not None:
            _stop_services(C)
        _release_mutex()


if __name__=='__main__':
    sys.exit(run_app())
'''
main=textwrap.dedent(main)
compile(main,str(main_path),"exec")
main_path.write_text(main,encoding="utf-8")

# Installer version only; user still installs this update once, after that normal
# desktop double-click is self-recovering and does not need reinstall.
t=iss_path.read_text(encoding="utf-8")
if "2.3.2" not in t and "2.3.3" not in t:
    raise SystemExit("No se encontró versión 2.3.2 en installer.iss")
t=t.replace("2.3.2","2.3.3")
iss_path.write_text(t,encoding="utf-8")
