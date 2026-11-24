# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# iOS accessibility backend: VoiceOver announcements and AVSpeechSynthesizer TTS.
# Supports iOS.

import ctypes
from .. import system
from .core import Provider


class IOSVoiceOver(Provider):
	name = "mobile_sr"
	priority = 10

	def is_active(self):
		if system.get_platform()["os"] != "ios":
			return False
		try:
			from rubicon.objc import ObjCClass
			return bool(ObjCClass("UIAccessibility").isVoiceOverRunning)
		except Exception:
			return False

	def speak(self, text, interrupt=False):
		if not text: return
		try:
			from rubicon.objc import ObjCClass
			ui = ctypes.CDLL("/System/Library/Frameworks/UIKit.framework/UIKit")
			ns_str = ObjCClass("NSString").stringWithUTF8String_(str(text).encode("utf-8"))
			ui.UIAccessibilityPostNotification(ctypes.c_uint32(1008), ctypes.c_void_p(ns_str.ptr.value))
		except Exception:
			pass


class IOSSpeech(Provider):
	name = "voiceover"
	priority = 80
	is_system_output = True
	capabilities = {
		"has_rate": True, "min_rate": 0, "max_rate": 100,
		"has_pitch": True, "min_pitch": 0, "max_pitch": 100,
		"has_volume": True, "min_volume": 0, "max_volume": 100,
		"has_voice": False, "has_pan": False, "min_pan": -100, "max_pan": 100,
		"has_output_device": False, "has_mono": False, "has_hrtf": False,
		"has_fx": False, "has_engine": False, "has_voice_language": False,
		"has_system_default": False,
	}

	def __init__(self):
		self._rate = 50
		self._pitch = 50
		self._volume = 100.0
		self._synth = None

	def _ensure(self):
		if self._synth is None:
			try:
				from rubicon.objc import ObjCClass
				self._synth = ObjCClass("AVSpeechSynthesizer").alloc().init()
			except Exception:
				self._synth = None
		return self._synth

	def is_active(self):
		return system.get_platform()["os"] == "ios"

	def speak(self, text, interrupt=False):
		if not text: return
		synth = self._ensure()
		if synth is None: return
		try:
			from rubicon.objc import ObjCClass
			if interrupt: synth.stopSpeakingAtBoundary_(0)
			utt = ObjCClass("AVSpeechUtterance").speechUtteranceWithString_(str(text))
			utt.rate = max(0.1, min(0.9, self._rate / 100.0))
			utt.pitchMultiplier = max(0.5, min(2.0, 0.5 + self._pitch / 50.0))
			utt.volume = max(0.0, min(1.0, self._volume / 100.0))
			synth.speakUtterance_(utt)
		except Exception:
			pass

	def silence(self):
		if self._synth is not None:
			try: self._synth.stopSpeakingAtBoundary_(0)
			except Exception: pass

	def get_rate(self): return self._rate
	def set_rate(self, value): self._rate = max(0, min(100, int(round(value)))); return True
	def get_pitch(self): return self._pitch
	def set_pitch(self, value): self._pitch = max(0, min(100, int(round(value)))); return True
	def get_volume(self): return self._volume
	def set_volume(self, value): self._volume = max(0.0, min(100.0, float(value))); return True


def create_providers():
	return [IOSVoiceOver(), IOSSpeech()]
