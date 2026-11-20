from __future__ import absolute_import
import os
import platform
import ctypes
import re
from xml.sax.saxutils import escape
from pyaudiogaming import system
from .base import Output

_PUNCT_PAUSE_RE = re.compile(r"(?<!\d)([,;:.!?]+(?:\s+[,;:.!?]+)*)(?=\s|$)")
_PUNCT_SPLIT_RE = re.compile(r"(?<!\d)[,;:.!?]+\s+\S")
_PUNCT_PAUSE_MS = {
    ",": 150,
    ";": 250,
    ":": 250,
    ".": 350,
    "!": 350,
    "?": 350,
}


class NVDA(Output):
    """Supports The NVDA screen reader"""

    name = "NVDA"
    lib32 = "nvdaControllerClient32.dll"
    lib64 = "nvdaControllerClient64.dll"
    argtypes = {
        "nvdaController_brailleMessage": (ctypes.c_wchar_p,),
        "nvdaController_speakText": (ctypes.c_wchar_p,),
        "nvdaController_speakSsml": (ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int, ctypes.c_bool),
        "nvdaController_setOnSsmlMarkReachedCallback": (ctypes.c_void_p,),
    }
    has_auto_pause = True

    def __init__(self):
        super(NVDA, self).__init__()
        self.helper_lib = None
        self.auto_pause = True
        self._mark_callback_ref = None

    def NVDAHelperLoader(self):
        arch = system.get_arch()
        li = "64A" if arch["is arm"] and arch["bit"] == 64 else arch["bit"]
        self.helper_lib = system.load_dll(f"nvdaHelperRemote{li}", ot="windows", WinDLL=True)
        try:
            if self.helper_lib:
                self.helper_lib.nvdaHelperRemote_sendKey.argtypes = (ctypes.c_short, ctypes.c_int)
                self.helper_lib.nvdaHelperRemote_logMessage.argtypes = (ctypes.c_int, ctypes.c_wchar_p)
                self.helper_lib.injectIntoProcess.argtypes = (ctypes.c_int,)
                self.helper_lib.nvdaHelper_uninjectFromProcess.argtypes = (ctypes.c_int,)                

                res = self.helper_lib.nvdaHelperRemote_connect()
                if res != 0:
                    print(f"NVDA Helper Remote connected with code: {res}")
                
            return self.helper_lib
        except Exception as e:
            print(f"Error loading NVDA Helper: {e}")
            return None

    def is_active(self):
        try:
            return self.lib.nvdaController_testIfRunning() == 0
        except:
            return False

    def braille(self, text, **options):
        self.lib.nvdaController_brailleMessage(text)

    def get_auto_pause(self):
        return self.auto_pause

    def set_auto_pause(self, enabled):
        self.auto_pause = bool(enabled)

    @staticmethod
    def _text_to_ssml(text):
        parts = []
        last = 0
        for match in _PUNCT_PAUSE_RE.finditer(text):
            token = match.group(1)
            parts.append(escape(text[last:match.end()]))
            ms = max((_PUNCT_PAUSE_MS.get(ch, 150) for ch in token if ch in _PUNCT_PAUSE_MS), default=200)
            parts.append(f'<break time="{ms}ms"/>')
            last = match.end()
        parts.append(escape(text[last:]))
        return f"<speak>{''.join(parts)}</speak>"

    def speak_ssml(self, ssml, symbol_level=-1, priority=0, asynchronous=True):
        if not self.lib or not hasattr(self.lib, "nvdaController_speakSsml"):
            return False
        try:
            return self.lib.nvdaController_speakSsml(str(ssml), int(symbol_level), int(priority), bool(asynchronous)) == 0
        except Exception:
            return False

    def set_on_ssml_mark_reached(self, callback):
        if not self.lib or not hasattr(self.lib, "nvdaController_setOnSsmlMarkReachedCallback"):
            return False
        if callback is None:
            self._mark_callback_ref = None
            return self.lib.nvdaController_setOnSsmlMarkReachedCallback(None) == 0
        cb_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_wchar_p)
        self._mark_callback_ref = cb_type(lambda name: int(bool(callback(name))))
        return self.lib.nvdaController_setOnSsmlMarkReachedCallback(self._mark_callback_ref) == 0

    def is_speaking(self):
        if not self.lib or not hasattr(self.lib, "nvdaController_isSpeaking"):
            return None
        speaking = ctypes.c_bool(False)
        if self.lib.nvdaController_isSpeaking(ctypes.byref(speaking)) == 0:
            return bool(speaking.value)
        return None

    def get_process_id(self):
        if not self.lib or not hasattr(self.lib, "nvdaController_getProcessId"):
            return None
        pid = ctypes.c_ulong(0)
        if self.lib.nvdaController_getProcessId(ctypes.byref(pid)) == 0:
            return int(pid.value)
        return None

    def speak(self, text, interrupt=False):
        if interrupt:
            self.silence()
        text = str(text)
        from pyaudiogaming import buffer
        if (
            self.auto_pause
            and getattr(buffer, "nvda_use_ssml", False)
            and _PUNCT_SPLIT_RE.search(text)
            and self.lib
            and hasattr(self.lib, "nvdaController_speakSsml")
        ):
            if self.speak_ssml(self._text_to_ssml(text), symbol_level=-1, priority=0, asynchronous=True):
                return
        self.lib.nvdaController_speakText(text)

    def silence(self):
        self.lib.nvdaController_cancelSpeech()

    def connect_remote(self):
        lib = self.helper_lib
        return lib.nvdaHelperRemote_connect() == 0 if lib else False

    def disconnect_remote(self):
        lib=self.helper_lib
        return lib.nvdaHelperRemote_disconnect() == 0 if lib else False

    def inject(self, pid):
        lib=self.helper_lib
        return lib.nvdaHelper_injectIntoProcess(pid) == 0 if lib else False

    def uninject(self, pid):
        lib=self.helper_lib
        return lib.nvdaHelper_uninjectFromProcess(pid) == 0 if lib else False

    def send_key(self, vk_code, is_extended=False):
        lib=self.helper_lib
        return lib.nvdaHelperRemote_sendKey(vk_code, 1 if is_extended else 0) == 0 if lib else False

    def resync(self):
        lib=self.helper_lib
        return lib.nvdaHelperLocal_resync() == 0 if lib else False

    def get_version_helper(self):
        lib=self.helper_lib
        if lib:
            try: return lib.nvdaHelperRemote_getVersion()
            except: return None
        return None

    def install_input_hook(self):
        lib=self.helper_lib
        return lib.nvdaHelperRemote_installInputHook() == 0 if lib else False

    def uninstall_input_hook(self):
        lib=self.helper_lib
        return lib.nvdaHelperRemote_uninstallInputHook() == 0 if lib else False

    def is_server_running(self):
        lib=self.helper_lib
        return lib.nvdaHelperRemote_isServerRunning() == 0 if lib else False

    def log_message(self, level, message):
        lib=self.helper_lib
        if lib:
            # level: 0=debug, 1=info, 2=warning, 3=error
            return lib.nvdaHelperRemote_logMessage(level, message) == 0
        return False

output_class = NVDA