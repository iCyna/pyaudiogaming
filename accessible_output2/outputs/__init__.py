from ... import system


os=system.get_platform()["os"]
if os == "windows":
	from . import nvda, jaws, window_eyes, zdsr, sapi5, pc_talker, system_access
elif os == "macos":
	from . import voiceover
elif os == "linux":
	from . import speech_dispatcher, e_speak
elif os == "android" or os == "ios":
	from . import android_tts
from . import auto
