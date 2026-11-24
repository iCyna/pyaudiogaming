# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Compact Linux SpeechDispatcher and eSpeak BASS-routed TTS drivers for g2access.
# Supports Linux.

import shutil
import subprocess
from .core import AudioPipeline, Provider


class SpeechDispatcherProvider(Provider):
	name = "speech_dispatcher"
	priority = 15

	def __init__(self):
		self._client = None
		try:
			import speechd
			self._client = speechd.SSIPClient("pyaudiogaming")
		except Exception:
			self._client = None

	def is_active(self): return self._client is not None

	def speak(self, text, interrupt=False):
		if self._client is None: return
		if interrupt: self.silence()
		try: self._client.speak(str(text))
		except Exception: pass

	def silence(self):
		if self._client is None: return
		try: self._client.cancel()
		except Exception: pass


class ESpeakProvider(Provider):
	name = "espeak"
	priority = 90
	is_system_output = True
	capabilities = {
		"has_rate": True, "min_rate": 0, "max_rate": 100,
		"has_pitch": True, "min_pitch": 0, "max_pitch": 100,
		"has_volume": True, "min_volume": 0, "max_volume": 100,
		"has_voice": True, "has_pan": True, "min_pan": -100, "max_pan": 100,
		"has_output_device": True, "has_mono": True, "has_hrtf": True,
		"has_fx": True, "has_engine": False, "has_voice_language": False,
		"has_system_default": False,
	}

	def __init__(self):
		self._bin = shutil.which("espeak-ng") or shutil.which("espeak")
		self._rate = 50
		self._pitch = 50
		self._voice_name = None
		self._voices = None
		self._direct_proc = None
		self._pipe = AudioPipeline(self._synth_wav, fallback_fn=self._speak_direct, stop_fallback_fn=self._stop_direct)

	def _stop_direct(self):
		p = self._direct_proc
		if p is not None and p.poll() is None:
			try:
				p.terminate()
			except Exception:
				pass

	def _speak_direct(self, text, interrupt=True):
		if not self._bin:
			return
		if interrupt and self._direct_proc is not None and self._direct_proc.poll() is None:
			try:
				self._direct_proc.terminate()
			except Exception:
				pass
		try:
			wpm = int(80 + self._rate * 3.2)
			cmd = [self._bin, "-s", str(wpm), "-p", str(self._pitch)]
			if self._voice_name:
				cmd.extend(["-v", self._voice_name])
			cmd.append(str(text))
			self._direct_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		except Exception:
			pass

	def _synth_wav(self, text):
		if not self._bin: return None
		try:
			wpm = int(80 + self._rate * 3.2)
			cmd = [self._bin, "--stdout", "-s", str(wpm), "-p", str(self._pitch)]
			if self._voice_name:
				cmd.extend(["-v", self._voice_name])
			cmd.append(str(text))
			res = subprocess.run(cmd, capture_output=True, timeout=4)
			return res.stdout if res.returncode == 0 and len(res.stdout) > 44 else None
		except Exception:
			return None

	def is_active(self): return bool(self._bin)

	def speak(self, text, interrupt=False):
		if not text or not self._bin: return
		key = (self._voice_name, self._rate, self._pitch, str(text))
		self._pipe.enqueue(str(text), key, interrupt=bool(interrupt))

	def speak3d(self, text, lx, ly, lz, sx, sy, sz, interrupt=False, **kwargs):
		if not text or not self._bin: return
		key = (self._voice_name, self._rate, self._pitch, str(text))
		self._pipe.enqueue(str(text), key, interrupt=bool(interrupt), spatial=(lx, ly, lz, sx, sy, sz, kwargs))

	def silence(self):
		self._pipe.stop()
		if self._direct_proc is not None and self._direct_proc.poll() is None:
			try:
				self._direct_proc.terminate()
			except Exception:
				pass
	def get_sound(self): return self._pipe.get_sound()

	def list_voices(self):
		if self._voices is None:
			out = []
			if self._bin:
				try:
					res = subprocess.run([self._bin, "--voices"], capture_output=True, text=True, timeout=3)
					for ln in res.stdout.splitlines()[1:]:
						parts = ln.split()
						if len(parts) >= 4:
							out.append(parts[3])
				except Exception:
					pass
			self._voices = out
		return list(self._voices)

	def get_voice(self): return self._voice_name
	def set_voice(self, value): self._voice_name = str(value) if value else None; self._pipe.clear_cache(); return True
	def get_rate(self): return self._rate
	def set_rate(self, value): self._rate = max(0, min(100, int(round(value)))); self._pipe.clear_cache(); return True
	def get_pitch(self): return self._pitch
	def set_pitch(self, value): self._pitch = max(0, min(100, int(round(value)))); self._pipe.clear_cache(); return True
	def get_volume(self): return self._pipe.volume
	def set_volume(self, value): self._pipe.volume = max(0.0, min(100.0, float(value))); return True
	def get_pan(self): return self._pipe.pan
	def set_pan(self, value): self._pipe.pan = max(-100.0, min(100.0, float(value))); return True
	def get_sound_pitch(self): return self._pipe.sound_pitch
	def set_sound_pitch(self, value): self._pipe.sound_pitch = float(value); return True
	def get_output_device(self): return self._pipe.output_device
	def set_output_device(self, value): self._pipe.output_device = int(value); return True
	def get_mono(self): return self._pipe.mono
	def set_mono(self, value): self._pipe.mono = bool(value); return True
	def get_hrtf(self): return self._pipe.hrtf
	def set_hrtf(self, value): self._pipe.hrtf = bool(value); return True
	def get_fx(self): return self._pipe.fx
	def set_fx(self, value): self._pipe.fx = value; return True
	def set_zone_fx_provider(self, provider): self._pipe.zone_fx_provider = provider; return True
	def get_auto_pause(self): return self._pipe.auto_pause
	def set_auto_pause(self, enabled): self._pipe.auto_pause = bool(enabled); return True


def create_providers():
	return [SpeechDispatcherProvider(), ESpeakProvider()]
