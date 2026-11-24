# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Compact Windows screen reader and SAPI5 BASS-routed TTS drivers for g2access.
# Supports Windows.

import atexit
import base64
import ctypes
import os
import platform
import subprocess
import tempfile
import threading
from .core import AudioPipeline, Provider, load_native_lib, pcm_to_wav


def _enum_sapi_tokens_com():
	"""Enumerate native-arch SAPI5 voice tokens via SpObjectTokenCategory (avoids SpVoice.GetVoices SPERR_NOT_FOUND)."""
	cat = _load_com("SAPI.SpObjectTokenCategory")
	if cat is not None:
		try:
			cat.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices", False)
			toks = cat.EnumerateTokens("", "")
			out = []
			for i in range(toks.Count):
				t = toks.Item(i)
				try:
					out.append((str(t.GetDescription()), t))
				except Exception:
					continue
			if out:
				return out
		except Exception:
			pass
	v = _load_com("SAPI.SpVoice")
	if v is not None:
		for args in (("", ""), ()):
			try:
				toks = v.GetVoices(*args)
				return [(str(toks.Item(i).GetDescription()), toks.Item(i)) for i in range(toks.Count)]
			except Exception:
				continue
	return []


def _scan_sapi32_registry_voices():
	"""Fast (<1ms) WOW6432Node registry scan for 32-bit SAPI5 voices on 64-bit Windows."""
	if platform.architecture()[0] != "64bit":
		return []
	try:
		import winreg
	except Exception:
		return []
	names = []
	seen = set()
	try:
		with winreg.OpenKey(
			winreg.HKEY_LOCAL_MACHINE,
			r"SOFTWARE\Microsoft\Speech\Voices\Tokens",
			0,
			winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
		) as k:
			idx = 0
			while True:
				try:
					sub = winreg.EnumKey(k, idx)
					idx += 1
					with winreg.OpenKey(k, sub) as sk:
						try:
							desc, _ = winreg.QueryValueEx(sk, "")
						except Exception:
							desc = sub
					desc = str(desc).strip()
					if desc and desc not in seen:
						seen.add(desc)
						names.append(desc)
				except OSError:
					break
	except Exception:
		pass
	return names


_SAPI32_VBS_SCRIPT = r"""
Option Explicit
Dim cat, toks, i, t, v, vmap, dom, b64enc, b64dec, stm, fmt44
Set vmap = CreateObject("Scripting.Dictionary")
Set cat = CreateObject("SAPI.SpObjectTokenCategory")
cat.SetId "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices", False
Set toks = cat.EnumerateTokens("", "")
For i = 0 To toks.Count - 1
    On Error Resume Next
    Set t = toks.Item(i)
    If Err.Number = 0 Then
        vmap(t.GetDescription()) = i
    End If
    Err.Clear
    On Error GoTo 0
Next
Set v = CreateObject("SAPI.SpVoice")
Set dom = CreateObject("MSXML2.DOMDocument")
Set b64enc = dom.createElement("e")
b64enc.dataType = "bin.base64"
Set b64dec = dom.createElement("d")
b64dec.dataType = "bin.base64"
Set stm = CreateObject("ADODB.Stream")
Set fmt44 = CreateObject("SAPI.SpAudioFormat")
fmt44.Type = 34

Function B64ToUtf8(s)
    If Len(s) = 0 Then
        B64ToUtf8 = ""
        Exit Function
    End If
    b64dec.text = s
    stm.Type = 1
    stm.Open
    stm.Write b64dec.nodeTypedValue
    stm.Position = 0
    stm.Type = 2
    stm.Charset = "utf-8"
    B64ToUtf8 = stm.ReadText
    stm.Close
End Function

WScript.StdOut.WriteLine "READY"
Dim line, parts, vname, rateVal, flagsVal, want44, txt, mem, wf, sr, ch, bps, rawB64
Do While Not WScript.StdIn.AtEndOfStream
    line = WScript.StdIn.ReadLine
    If line = "QUIT" Then Exit Do
    On Error Resume Next
    parts = Split(line, "|", 5)
    If UBound(parts) >= 4 Then
        vname = B64ToUtf8(parts(0))
        rateVal = CLng(parts(1))
        flagsVal = CLng(parts(2))
        want44 = CLng(parts(3))
        txt = B64ToUtf8(parts(4))
        If Len(vname) > 0 And vmap.Exists(vname) Then
            Set v.Voice = toks.Item(vmap(vname))
        End If
        v.Rate = rateVal
        v.Volume = 100
        Set mem = CreateObject("SAPI.SpMemoryStream")
        If want44 <> 0 Then Set mem.Format = fmt44
        Set v.AudioOutputStream = mem
        v.Speak txt, flagsVal
        If Err.Number <> 0 Then
            WScript.StdOut.WriteLine "ERR:" & Err.Number
            Err.Clear
        Else
            b64enc.nodeTypedValue = mem.GetData()
            Set wf = mem.Format.GetWaveFormatEx()
            sr = CLng(wf.SamplesPerSec)
            ch = CLng(wf.Channels)
            bps = CLng(wf.BitsPerSample)
            If sr <= 0 Then sr = 22050
            If ch <= 0 Then ch = 1
            If bps <= 0 Then bps = 16
            rawB64 = Replace(Replace(b64enc.text, vbCr, ""), vbLf, "")
            WScript.StdOut.WriteLine "OK:" & sr & ":" & ch & ":" & bps & ":" & rawB64
        End If
    Else
        WScript.StdOut.WriteLine "ERR:bad_req"
    End If
    On Error GoTo 0
Loop
"""


class _Sapi32Worker:
	"""On-demand persistent 32-bit SAPI5 worker via native SysWOW64 cscript.exe (fast start, zero .NET)."""
	_CSCRIPT32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64", "cscript.exe")

	def __init__(self):
		self._lock = threading.Lock()
		self._proc = None
		self._script_path = None
		atexit.register(self.close)

	def _ensure(self):
		if self._proc is not None and self._proc.poll() is None:
			return True
		if not os.path.isfile(self._CSCRIPT32):
			return False
		try:
			if not self._script_path or not os.path.isfile(self._script_path):
				tf = tempfile.NamedTemporaryFile(prefix="g2sapi32_", suffix=".vbs", mode="w", encoding="utf-8", delete=False)
				tf.write(_SAPI32_VBS_SCRIPT)
				tf.close()
				self._script_path = tf.name
			flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
			self._proc = subprocess.Popen(
				[self._CSCRIPT32, "//Nologo", self._script_path],
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.DEVNULL,
				text=True,
				encoding="ascii",
				creationflags=flags,
			)
			ready = self._proc.stdout.readline().strip()
			if ready != "READY":
				self.close()
				return False
			return True
		except Exception:
			self.close()
			return False

	def synth_pcm(self, voice_name, rate_sapi, text, flags=0, want_44k=False):
		with self._lock:
			if not self._ensure():
				return None
			try:
				v_b64 = base64.b64encode((voice_name or "").encode("utf-8")).decode("ascii")
				t_b64 = base64.b64encode(str(text).encode("utf-8")).decode("ascii")
				req = f"{v_b64}|{int(rate_sapi)}|{int(flags)}|{1 if want_44k else 0}|{t_b64}\n"
				self._proc.stdin.write(req)
				self._proc.stdin.flush()
				resp = self._proc.stdout.readline().strip()
				if resp.startswith("OK:"):
					parts = resp.split(":", 4)
					if len(parts) == 5:
						sr, ch, bps = int(parts[1]), int(parts[2]), int(parts[3])
						return base64.b64decode(parts[4]), sr, ch, bps
			except Exception:
				self.close()
			return None

	def close(self):
		p = self._proc
		self._proc = None
		if p is not None:
			try:
				if p.poll() is None:
					try:
						p.stdin.write("QUIT\n")
						p.stdin.flush()
					except Exception:
						pass
					p.terminate()
			except Exception:
				pass
		sp = self._script_path
		self._script_path = None
		if sp:
			try:
				if os.path.exists(sp):
					os.unlink(sp)
			except Exception:
				pass


def _load_com(prog_id):
	try:
		import pythoncom
		pythoncom.CoInitialize()
	except Exception:
		pass
	try:
		import win32com.client.dynamic
		return win32com.client.dynamic.Dispatch(prog_id)
	except Exception:
		try:
			import comtypes.client
			return comtypes.client.CreateObject(prog_id)
		except Exception:
			return None


class NVDAProvider(Provider):
	name = "nvda"
	priority = 10

	def __init__(self):
		self.lib = load_native_lib("nvdaControllerClient32.dll", "nvdaControllerClient64.dll")
		if self.lib is not None:
			try:
				self.lib.nvdaController_speakText.argtypes = (ctypes.c_wchar_p,)
				self.lib.nvdaController_brailleMessage.argtypes = (ctypes.c_wchar_p,)
			except Exception:
				pass

	def is_active(self):
		if self.lib is None: return False
		try: return self.lib.nvdaController_testIfRunning() == 0
		except Exception: return False

	def speak(self, text, interrupt=False):
		if self.lib is None: return
		if interrupt: self.silence()
		try: self.lib.nvdaController_speakText(str(text))
		except Exception: pass

	def braille(self, text):
		if self.lib is None: return
		try: self.lib.nvdaController_brailleMessage(str(text))
		except Exception: pass

	def silence(self):
		if self.lib is None: return
		try: self.lib.nvdaController_cancelSpeech()
		except Exception: pass


class ZDSRProvider(Provider):
	name = "zdsr"
	priority = 15

	def __init__(self):
		self.lib = load_native_lib("ZDSRAPI.dll", "ZDSRAPI_x64.dll")
		if self.lib is not None:
			try: self.lib.InitTTS(0, "")
			except Exception: pass

	def is_active(self):
		if self.lib is None: return False
		try: return self.lib.GetSpeakState() != 2
		except Exception: return False

	def speak(self, text, interrupt=False):
		if self.lib is None: return
		try: self.lib.Speak(str(text), bool(interrupt))
		except Exception: pass

	def silence(self):
		if self.lib is None: return
		try: self.lib.StopSpeak()
		except Exception: pass


class JAWSProvider(Provider):
	name = "jaws"
	priority = 20

	def __init__(self):
		self._obj = None
		self._checked = False

	def _ensure(self):
		if not self._checked:
			self._checked = True
			self._obj = _load_com("FreedomSci.JawsApi")
		return self._obj

	def is_active(self):
		try:
			return bool(ctypes.windll.user32.FindWindowW("JFWUI2", None)) and self._ensure() is not None
		except Exception:
			return False

	def speak(self, text, interrupt=False):
		obj = self._ensure()
		if obj is not None:
			try: obj.SayString(str(text), bool(interrupt))
			except Exception: pass

	def braille(self, text):
		obj = self._ensure()
		if obj is not None:
			try: obj.RunFunction(f'BrailleString("{str(text).replace(chr(34), chr(39))}")')
			except Exception: pass

	def silence(self):
		obj = self._ensure()
		if obj is not None:
			try: obj.StopSpeech()
			except Exception: pass


class SystemAccessProvider(Provider):
	name = "system_access"
	priority = 25

	def __init__(self):
		self.lib = load_native_lib("SAAPI32.dll", "SAAPI64.dll")

	def is_active(self):
		if self.lib is None: return False
		try: return bool(self.lib.SA_IsRunning())
		except Exception: return False

	def speak(self, text, interrupt=False):
		if self.lib is None: return
		try: self.lib.SA_SayW(str(text))
		except Exception: pass

	def braille(self, text):
		if self.lib is None: return
		try: self.lib.SA_BrlShowTextW(str(text))
		except Exception: pass

	def silence(self):
		if self.lib is None: return
		try: self.lib.SA_StopAudio()
		except Exception: pass


class DolphinProvider(Provider):
	name = "dolphin"
	priority = 30

	def __init__(self):
		self.lib = load_native_lib("dolapi.dll")

	def is_active(self):
		if self.lib is None: return False
		try: return self.lib.DolAccess_GetSystem() in (1, 4, 8)
		except Exception: return False

	def speak(self, text, interrupt=False):
		if self.lib is None: return
		if interrupt: self.silence()
		s = str(text)
		try: self.lib.DolAccess_Command(ctypes.c_wchar_p(s), (len(s) * 2) + 2, 1)
		except Exception: pass

	def silence(self):
		if self.lib is None: return
		try: self.lib.DolAccess_Action(141)
		except Exception: pass


class PCTalkerProvider(Provider):
	name = "pc_talker"
	priority = 35

	def __init__(self):
		self.lib = load_native_lib("PCTKUSR.dll", "PCTKUSR64.dll")

	def is_active(self):
		if self.lib is None: return False
		try: return self.lib.PCTKStatus() != 0
		except Exception: return False

	def speak(self, text, interrupt=False):
		if self.lib is None: return
		if interrupt: self.silence()
		try: self.lib.PCTKPRead(str(text).encode("cp932", "replace"), 0, 1)
		except Exception: pass

	def silence(self):
		if self.lib is None: return
		try: self.lib.PCTKVReset()
		except Exception: pass


class SAPI5Provider(Provider):
	name = "sapi5"
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
		self._com_lock = threading.RLock()
		self._tls = threading.local()
		self._rate = 50
		self._pitch = 50
		self._voice_name = None
		self._voices = None
		self._voices_64 = set()
		self._voices_32 = set()
		self._worker32 = _Sapi32Worker()
		self._direct_voice = None
		self._pipe = AudioPipeline(self._synth_wav, fallback_fn=self._speak_direct, stop_fallback_fn=self._stop_direct_sapi)

	def _format_speak_args(self, text):
		pitch_shift = int(round((self._pitch - 50) / 5.0))
		if pitch_shift != 0:
			esc = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
			return f'<pitch absmiddle="{pitch_shift}"/>{esc}', 8
		return str(text), 0

	@staticmethod
	def _rate_to_sapi(val):
		v = max(0.0, min(100.0, float(val)))
		if v <= 50.0:
			return int(round(-10.0 + (v / 50.0) * 10.0))
		return int(round(((v - 50.0) / 50.0) * 30.0))

	def _get_cached_voice(self):
		"""Reuse per-thread COM SpVoice + token map (5x faster than recreating COM every speak)."""
		v = getattr(self._tls, "sp_voice", None)
		if v is None:
			v = _load_com("SAPI.SpVoice")
			if v is None:
				return None
			self._tls.sp_voice = v
			self._tls.tok_map = {desc: tok for desc, tok in _enum_sapi_tokens_com()}
			self._tls.last_voice_name = None
			self._tls.fmt44 = None
		try:
			sapi_r = self._rate_to_sapi(self._rate)
			try:
				v.Rate = sapi_r
			except Exception:
				v.Rate = max(-10, min(10, sapi_r))
			v.Volume = 100
			if self._voice_name and self._voice_name != getattr(self._tls, "last_voice_name", None):
				tok = self._tls.tok_map.get(self._voice_name)
				if tok is not None:
					v.Voice = tok
					try:
						v.AudioOutput = v.AudioOutput
					except Exception:
						pass
					self._tls.last_voice_name = self._voice_name
		except Exception:
			pass
		return v

	def _synth_wav_64(self, text, want_44k=False):
		with self._com_lock:
			v = self._get_cached_voice()
			mem = _load_com("SAPI.SpMemoryStream")
			if v is None or mem is None:
				return None
			try:
				if want_44k:
					fmt = getattr(self._tls, "fmt44", None)
					if fmt is None:
						fmt = _load_com("SAPI.SpAudioFormat")
						if fmt is not None:
							fmt.Type = 34  # SAFT44kHz16BitMono to match Steam Audio HRTF
							self._tls.fmt44 = fmt
					if fmt is not None:
						mem.Format = fmt
				v.AudioOutputStream = mem
				speak_text, flags = self._format_speak_args(text)
				v.Speak(speak_text, flags)
				raw = bytes(mem.GetData())
				sr, ch, bps = (44100 if want_44k else 22050), 1, 16
				try:
					wf = mem.Format.GetWaveFormatEx()
					if wf is not None:
						sr = int(wf.SamplesPerSec) or sr
						ch = int(wf.Channels) or 1
						bps = int(wf.BitsPerSample) or 16
				except Exception:
					pass
				return pcm_to_wav(raw, sr, ch, bps) if raw else None
			except Exception:
				return None

	def _synth_wav_32(self, text, want_44k=False):
		rate_sapi = max(-10, min(10, self._rate_to_sapi(self._rate)))
		speak_text, flags = self._format_speak_args(text)
		res = self._worker32.synth_pcm(self._voice_name, rate_sapi, speak_text, flags=flags, want_44k=want_44k)
		if not res:
			return None
		raw, sr, ch, bps = res
		return pcm_to_wav(raw, sr, ch, bps) if raw else None

	def _synth_wav(self, text):
		if self._voices is None:
			self.list_voices()
		vname = self._voice_name
		# Keep native voice sample rate (no SAPI5 linear resampling)
		want_44k = False
		# Route 32-bit-only voices directly to the persistent 32-bit worker
		if vname and vname in self._voices_32 and vname not in self._voices_64:
			return self._synth_wav_32(text, want_44k=want_44k)
		wav = self._synth_wav_64(text, want_44k=want_44k)
		if wav:
			return wav
		# Automatic fallback to 32-bit SAPI5 if a 64-bit COM voice failed (e.g. REGDB_E_CLASSNOTREG)
		if vname and vname in self._voices_32:
			return self._synth_wav_32(text, want_44k=want_44k)
		return None

	def _needs_bass_pipeline(self):
		if self._voices is None:
			self.list_voices()
		vname = self._voice_name
		if vname and vname in self._voices_32 and vname not in self._voices_64:
			return True
		p = self._pipe
		# Note: hrtf only applies to speak3d(), NOT dry 2D speak()
		if p.mono or p._resolve_fx():
			return True
		if abs(float(p.pan)) > 0.01 or abs(float(p.sound_pitch) - 100.0) > 0.01:
			return True
		if p.output_device is not None and int(p.output_device) >= 0:
			return True
		return False

	def _speak_direct(self, text, interrupt=True):
		with self._com_lock:
			v = self._get_cached_voice()
			if v is None:
				return
			self._direct_voice = v
			try:
				v.AudioOutputStream = None
				v.Volume = max(0, min(100, int(round(self._pipe.volume))))
				speak_text, flags = self._format_speak_args(text)
				# SVSFlagsAsync=1, SVSFPurgeBeforeSpeak=2
				sapi_flags = flags | 1 | (2 if interrupt else 0)
				v.Speak(speak_text, sapi_flags)
			except Exception:
				pass

	def _stop_direct_sapi(self):
		with self._com_lock:
			for v in (getattr(self._tls, "sp_voice", None), self._direct_voice):
				if v is not None:
					try:
						v.Speak("", 3)  # SVSFlagsAsync | SVSFPurgeBeforeSpeak
					except Exception:
						pass

	def is_active(self):
		return True

	def speak(self, text, interrupt=False):
		if not text:
			return
		# Always non-blocking (<0.1ms on main thread); worker thread handles COM + BASS PCM
		key = (self._voice_name, self._rate, self._pitch, str(text))
		self._pipe.enqueue(str(text), key, interrupt=bool(interrupt))

	def speak3d(self, text, lx, ly, lz, sx, sy, sz, interrupt=False, **kwargs):
		if not text:
			return
		key = (self._voice_name, self._rate, self._pitch, str(text))
		self._pipe.enqueue(str(text), key, interrupt=bool(interrupt), spatial=(lx, ly, lz, sx, sy, sz, kwargs))

	def silence(self):
		self._pipe.stop()
		if self._pipe._fallback_active:
			self._pipe._fallback_active = False
			self._stop_direct_sapi()

	def get_sound(self): return self._pipe.get_sound()

	def list_voices(self):
		if self._voices is None:
			names = []
			seen = set()
			self._voices_64 = set()
			self._voices_32 = set()
			for desc, _ in _enum_sapi_tokens_com():
				self._voices_64.add(desc)
				if desc not in seen:
					seen.add(desc)
					names.append(desc)
			for desc in _scan_sapi32_registry_voices():
				self._voices_32.add(desc)
				if desc not in seen:
					seen.add(desc)
					names.append(desc)
			self._voices = names
		return list(self._voices)

	def get_voice(self):
		if self._voice_name is None:
			vs = self.list_voices()
			self._voice_name = vs[0] if vs else None
		return self._voice_name

	def set_voice(self, value):
		self._voice_name = str(value) if value else None
		self._pipe.clear_cache()
		return True

	def get_rate(self): return self._rate
	def set_rate(self, value):
		self._rate = max(0, min(100, int(round(value))))
		self._pipe.clear_cache()
		return True

	def get_pitch(self): return self._pitch
	def set_pitch(self, value):
		self._pitch = max(0, min(100, int(round(value))))
		self._pipe.clear_cache()
		return True

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
	return [
		NVDAProvider(), ZDSRProvider(), JAWSProvider(),
		SystemAccessProvider(), DolphinProvider(), PCTalkerProvider(),
		SAPI5Provider(),
	]
