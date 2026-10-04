from __future__ import absolute_import
from pyaudiogaming import system as s
if s.get_platform()["os"] == "windows":
    from libloader import com
    from libloader.com import load_com

    def _load_com(*names):
        try:
            return load_com(*names)
        except AttributeError:
            # remove cache
            import os
            import sys
            import shutil
            for module in [m.__name__ for m in sys.modules.values()]:
                if module.startswith("win32com.gen_py."):
                    del sys.modules[module]
            shutil.rmtree(os.path.join(os.environ.get('LOCALAPPDATA'), 'Temp', 'gen_py'))
            # try again
            return load_com(*names)
    com.load_com = _load_com

    from . import nvda
    from . import jaws
    from . import sapi5
    from . import window_eyes
    from . import system_access
    from . import dolphin
    from . import pc_talker
    from . import zdsr

    # import sapi4

if s.get_platform()["os"] == "macos" or s.get_platform() == "ios":
    from . import voiceover

if s.get_platform()["os"] == "linux":
    from . import speech_dispatcher
    from . import e_speak
if s.get_platform()["os"] == "android":
    from . import android_tts
from . import auto
