# -*- coding: utf-8 -*-
"""Android/iOS TTS output backed by native Android TextToSpeech (BeeWare/Chaquopy) with Plyer fallback."""
import threading
from .base import Output
from pyaudiogaming import system

try:
    from java import jclass as _jclass, dynamic_proxy as _dynamic_proxy
    _HAS_JAVA = True
except Exception:
    _jclass = None
    _dynamic_proxy = None
    _HAS_JAVA = False

try:
    from plyer import tts as _plyer_tts
except Exception:
    _plyer_tts = None


class Android_TTS(Output):
    """Trình đọc màn hình dành riêng cho Mobile (Android/iOS)."""
    name = "Android_TTS"
    priority = 100

    def __init__(self):
        super().__init__()
        self._tts = None
        self._ready = False
        self._lock = threading.Lock()
        self._pending = []
        self._listener = None
        self._rate = 1.0
        self._pitch = 1.0
        self._init_native_tts()

    def _get_context(self):
        if not _HAS_JAVA:
            return None
        try:
            cls = _jclass("org.beeware.android.MainActivity")
            act = getattr(cls, "singletonThis", None)
            if act is not None:
                return act
        except Exception:
            pass
        try:
            Python = _jclass("com.chaquo.python.Python")
            platform = Python.getPlatform()
            if hasattr(platform, "getApplication"):
                return platform.getApplication()
        except Exception:
            pass
        return None

    def _init_native_tts(self):
        if not _HAS_JAVA:
            return
        ctx = self._get_context()
        if ctx is None:
            return
        try:
            TextToSpeech = _jclass("android.speech.tts.TextToSpeech")
            OnInitListener = _jclass("android.speech.tts.TextToSpeech$OnInitListener")
            self_ref = self

            class _InitListener(_dynamic_proxy(OnInitListener)):
                def onInit(self, status):
                    if int(status) == TextToSpeech.SUCCESS:
                        with self_ref._lock:
                            self_ref._ready = True
                            queued = list(self_ref._pending)
                            self_ref._pending.clear()
                        for txt, intr in queued:
                            self_ref._speak_native(txt, intr)

            self._listener = _InitListener()
            self._tts = TextToSpeech(ctx, self._listener)
        except Exception as exc:
            print(f"[Android_TTS] Native TextToSpeech init failed: {exc}")
            self._tts = None

    def _speak_native(self, text, interrupt=False):
        if self._tts is None:
            return False
        try:
            TextToSpeech = _jclass("android.speech.tts.TextToSpeech")
            mode = TextToSpeech.QUEUE_FLUSH if interrupt else TextToSpeech.QUEUE_ADD
            self._tts.speak(str(text), mode, None, None)
            return True
        except Exception:
            try:
                TextToSpeech = _jclass("android.speech.tts.TextToSpeech")
                mode = TextToSpeech.QUEUE_FLUSH if interrupt else TextToSpeech.QUEUE_ADD
                self._tts.speak(str(text), mode, None)
                return True
            except Exception:
                return False

    def is_active(self):
        os_info = system.get_platform()["os"]
        return os_info in ("android", "ios")

    def speak(self, text, interrupt=False):
        msg = str(text)
        if not msg:
            return
        try:
            import pygame
            if hasattr(pygame, "_android_bridge") and hasattr(pygame._android_bridge, "set_overlay_text"):
                pygame._android_bridge.set_overlay_text(msg, is_error=False)
        except Exception:
            pass
        if _HAS_JAVA and self._tts is None:
            self._init_native_tts()
        if self._tts is not None:
            with self._lock:
                if not self._ready:
                    if interrupt:
                        self._pending.clear()
                    self._pending.append((msg, bool(interrupt)))
                    return
            if self._speak_native(msg, interrupt):
                return
        if _plyer_tts is not None:
            try:
                _plyer_tts.speak(msg)
            except Exception:
                pass

    def silence(self):
        with self._lock:
            self._pending.clear()
        if self._tts is not None:
            try:
                self._tts.stop()
            except Exception:
                pass

    def get_rate(self):
        return self._rate

    def set_rate(self, rate):
        try:
            self._rate = max(0.25, min(4.0, float(rate)))
            if self._tts is not None:
                self._tts.setSpeechRate(float(self._rate))
        except Exception:
            pass

    def get_pitch(self):
        return self._pitch

    def set_pitch(self, pitch):
        try:
            self._pitch = max(0.25, min(4.0, float(pitch)))
            if self._tts is not None:
                self._tts.setPitch(float(self._pitch))
        except Exception:
            pass


output_class = Android_TTS
