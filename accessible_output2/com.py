"""Optional Windows COM support without generated cache files."""
import threading
from .. import system
_state = threading.local()

def load_com(*names):
    if system.get_platform()["os"] != "windows": raise OSError("COM requires Windows")
    import pythoncom
    from win32com.client.dynamic import Dispatch
    if not getattr(_state, "ready", False):
        pythoncom.CoInitialize()
        _state.ready = True
    errors = []
    for name in names:
        try: return Dispatch(name)
        except pythoncom.com_error as error: errors.append(str(error))
    raise pythoncom.com_error(-2147221164, "; ".join(errors), None, None)
