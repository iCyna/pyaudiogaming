# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# macOS accessibility backend: BASS-routed Speech synthesis via /usr/bin/say.
# Supports macOS.

import os
import shutil
import subprocess
import tempfile
from .. import system
from .core import AudioPipeline, Provider


class MacOSSpeech(Provider):
	name = "voiceover"
	priority = 80
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
		say_bin = shutil.which("say") or "/usr/bin/say"
		if not os.path.isfile(say_bin):
			return
		if interrupt and self._direct_proc is not None and self._direct_proc.poll() is None:
			try:
				self._direct_proc.terminate()
			except Exception:
				pass
		try:
			wpm = int(100 + self._rate * 3)
			cmd = [say_bin, "-r", str(wpm)]
			if self._voice_name:
				cmd.extend(["-v", self._voice_name])
			cmd.append(str(text))
			self._direct_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		except Exception:
			pass

	def _synth_wav(self, text):
		say_bin = shutil.which("say") or "/usr/bin/say"
		if not os.path.isfile(say_bin):
			return None
		tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
		tmp_path = tmp.name
		tmp.close()
		try:
			wpm = int(100 + self._rate * 3)
			cmd = [say_bin, "-r", str(wpm), "--data-format=LEI16@44100", "--file-format=WAVE", "-o", tmp_path]
			if self._voice_name:
				cmd.extend(["-v", self._voice_name])
			cmd.append(str(text))
			subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
			with open(tmp_path, "rb") as f:
				return f.read()
		except Exception:
			return None
		finally:
			try: os.unlink(tmp_path)
			except Exception: pass

	def is_active(self):
		return system.get_platform()["os"] == "macos"

	def speak(self, text, interrupt=False):
		if not text: return
		key = (self._voice_name, self._rate, self._pitch, str(text))
		self._pipe.enqueue(str(text), key, interrupt=bool(interrupt))

	def speak3d(self, text, lx, ly, lz, sx, sy, sz, interrupt=False, **kwargs):
		if not text: return
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
			try:
				import re
				res = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=3)
				for ln in res.stdout.splitlines():
					m = re.match(r"^\s*(.+?)\s+[a-z]{2,3}[_-][A-Z0-9]{2,}\s+#", ln)
					if m:
						out.append(m.group(1).strip())
					elif ln.strip():
						out.append(ln.split()[0])
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
	return [MacOSSpeech()]
