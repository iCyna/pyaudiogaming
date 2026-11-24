# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Android accessibility backend: BASS-routed Android_TTS and TalkBack Screen Reader.
# Supports Android.

from collections import OrderedDict, deque
import os
import tempfile
import threading
import time
import uuid
import wave

from .. import system
from .core import Provider

BASS_STREAMPROC_END = 0x80000000

try:
	from java import jclass as _jclass, dynamic_proxy as _dynamic_proxy
	_HAS_JAVA = True
except Exception:
	_jclass = None
	_dynamic_proxy = None
	_HAS_JAVA = False


class AndroidTTS(Provider):
	"""Android TTS matching accessible_output2 Android_TTS: Media-stream BASS PCM + parallel TalkBack."""
	name = "Android_TTS"
	aliases = ("android_tts",)
	priority = 100
	is_system_output = True
	capabilities = {
		"has_rate": True, "min_rate": 0, "max_rate": 100,
		"has_pitch": True, "min_pitch": 0, "max_pitch": 100,
		"has_volume": True, "min_volume": 0, "max_volume": 100,
		"has_voice": True, "has_pan": True, "min_pan": -100, "max_pan": 100,
		"has_output_device": True, "has_mono": True, "has_hrtf": True,
		"has_fx": True, "has_engine": True, "has_voice_language": True,
		"has_system_default": True,
	}

	def __init__(self):
		self._tts = None
		self._ready = False
		self._lock = threading.Lock()
		self._cond = threading.Condition()
		self._queue = deque()
		self._speak_seq = 0
		self._voices = OrderedDict()
		self._voice_names = []
		self._voice_locales = {}
		self._voice_languages = ["All"]
		self._voice_language = "All"
		self._voice_name = "System default"
		self._pending_voice = None
		self._pending_engine = None
		self._engines = OrderedDict([("System default", "")])
		self._engine_name = "System default"
		self._engine_pkg = ""
		self._use_system_default = False
		self._rate = 50
		self._pitch = 50
		self._volume = 100
		self._sound_pitch = 100.0
		self._pan = 0.0
		self._mono = False
		self._hrtf = False
		self._fx = None
		self._zone_fx_provider = None
		self._output_device = -1
		self._auto_pause = False
		self._bass_lock = threading.Lock()
		self._bass_sound = None
		self._listener = None
		self._utt_listener = None
		self._utt_events = {}
		self._utt_lock = threading.Lock()
		self._cache_dir = None
		self._synth_supported = True

		if system.get_platform()["os"] == "android" and _HAS_JAVA:
			self._init_native_tts()
		self._worker = threading.Thread(target=self._worker_loop, name="G2AndroidTTS", daemon=True)
		self._worker.start()

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
			plat = Python.getPlatform()
			if hasattr(plat, "getApplication"):
				return plat.getApplication()
		except Exception:
			pass
		return None

	@staticmethod
	def _rate_to_android(val):
		val = max(0.0, min(100.0, float(val)))
		if val >= 50.0:
			return max(0.25, min(4.0, 1.0 + ((val - 50.0) / 50.0) * 3.0))
		return max(0.25, min(4.0, 0.25 + (val / 50.0) * 0.75))

	@staticmethod
	def _pitch_to_android(val):
		val = max(0.0, min(100.0, float(val)))
		return max(0.5, min(2.0, 2.0 ** ((val - 50.0) / 50.0)))

	def _configure_media_audio_attributes(self):
		if not _HAS_JAVA or self._tts is None:
			return
		try:
			AudioAttributes = _jclass("android.media.AudioAttributes")
			Builder = _jclass("android.media.AudioAttributes$Builder")
			attrs = (
				Builder()
				.setUsage(AudioAttributes.USAGE_MEDIA)
				.setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
				.build()
			)
			self._tts.setAudioAttributes(attrs)
		except Exception:
			pass

	def _load_android_engines(self):
		engines = OrderedDict([("System default", "")])
		if not _HAS_JAVA or self._tts is None:
			return engines
		try:
			elist = self._tts.getEngines()
			if elist is not None:
				for idx in range(int(elist.size())):
					eng = elist.get(idx)
					pkg = str(getattr(eng, "name", "") or "")
					lbl = str(getattr(eng, "label", "") or pkg)
					if pkg:
						key = lbl if lbl not in engines else f"{lbl} ({pkg})"
						engines[key] = pkg
		except Exception:
			pass
		return engines

	def _load_android_voices(self):
		voices = OrderedDict()
		locales = {}
		if not _HAS_JAVA or self._tts is None:
			return voices, locales
		try:
			vset = self._tts.getVoices()
			if vset is not None:
				for v in vset.toArray():
					try:
						vname = str(v.getName())
						if vname:
							voices[vname] = v
							loc = v.getLocale()
							tag = ""
							if loc is not None:
								try:
									tag = str(loc.toLanguageTag() or "")
								except Exception:
									tag = str(loc.toString() or "").replace("_", "-")
							locales[vname] = tag
					except Exception:
						continue
		except Exception:
			pass
		try:
			cur = self._tts.getVoice()
			if cur is not None:
				cur_name = str(cur.getName())
				if cur_name and cur_name not in voices:
					voices[cur_name] = cur
					locales[cur_name] = ""
		except Exception:
			pass
		return voices, locales

	def _init_native_tts(self, engine_pkg=""):
		if not _HAS_JAVA:
			return
		ctx = self._get_context()
		if ctx is None:
			return
		try:
			if self._tts is not None:
				try:
					self._tts.stop()
					self._tts.shutdown()
				except Exception:
					pass
				self._tts = None
				self._ready = False
			try:
				cdir = ctx.getCacheDir()
				if cdir is not None:
					self._cache_dir = str(cdir.getAbsolutePath())
			except Exception:
				self._cache_dir = tempfile.gettempdir()

			TextToSpeech = _jclass("android.speech.tts.TextToSpeech")
			OnInitListener = _jclass("android.speech.tts.TextToSpeech$OnInitListener")
			OnUttCompleted = _jclass("android.speech.tts.TextToSpeech$OnUtteranceCompletedListener")
			self_ref = self

			class _UttListener(_dynamic_proxy(OnUttCompleted)):
				def onUtteranceCompleted(self, utteranceId):
					uid = str(utteranceId)
					with self_ref._utt_lock:
						ev = self_ref._utt_events.get(uid)
					if ev is not None:
						ev.set()

			class _InitListener(_dynamic_proxy(OnInitListener)):
				def onInit(self, status):
					if int(status) == TextToSpeech.SUCCESS:
						self_ref._configure_media_audio_attributes()
						try:
							self_ref._tts.setOnUtteranceCompletedListener(self_ref._utt_listener)
						except Exception:
							pass
						if not self_ref._use_system_default:
							try:
								self_ref._tts.setSpeechRate(float(self_ref._rate_to_android(self_ref._rate)))
								self_ref._tts.setPitch(float(self_ref._pitch_to_android(self_ref._pitch)))
							except Exception:
								pass
						# Mark ready IMMEDIATELY so first menu speech plays in <100ms (do NOT block on 500-voice JNI scan!)
						with self_ref._lock:
							self_ref._ready = True
						with self_ref._cond:
							self_ref._cond.notify_all()
						# Load engines/voices and apply pending voice/engine asynchronously in background
						threading.Thread(target=self_ref._bg_load_catalog_and_apply, name="G2AndroidTTSCat", daemon=True).start()

			self._utt_listener = _UttListener()
			self._listener = _InitListener()
			if engine_pkg:
				self._tts = TextToSpeech(ctx, self._listener, str(engine_pkg))
			else:
				self._tts = TextToSpeech(ctx, self._listener)
		except Exception:
			self._tts = None

	def _bg_load_catalog_and_apply(self):
		"""Background catalog scan (engines/voices) + pending settings apply without stalling first speech."""
		if self._tts is None or not self._ready:
			return
		try:
			cur_default_pkg = ""
			try:
				cur_default_pkg = str(self._tts.getDefaultEngine() or "")
			except Exception:
				cur_default_pkg = ""
			engines = self._load_android_engines()
			need_reinit_pkg = None
			with self._lock:
				self._engines = engines
				if self._pending_engine:
					pe = self._pending_engine
					self._pending_engine = None
					target_pkg = None
					target_lbl = None
					if pe in engines:
						target_lbl, target_pkg = pe, engines[pe]
					else:
						for k_lbl, k_pkg in engines.items():
							if k_pkg == pe:
								target_lbl, target_pkg = k_lbl, k_pkg
								break
					active_pkg = self._engine_pkg or cur_default_pkg
					if target_pkg:
						self._engine_name = target_lbl
						self._engine_pkg = target_pkg
						# Only re-init TTS if saved engine is ACTUALLY DIFFERENT from active engine!
						if target_pkg != active_pkg:
							need_reinit_pkg = target_pkg
			if need_reinit_pkg is not None:
				self._enqueue("engine", need_reinit_pkg)
				return
			voices, locales = self._load_android_voices()
			langs = ["All"] + sorted({tg for tg in locales.values() if tg})
			with self._lock:
				self._voices = voices
				self._voice_names = list(voices.keys())
				self._voice_locales = locales
				self._voice_languages = langs
				if self._voice_language not in langs:
					self._voice_language = "All"
				want_v = self._pending_voice or self._voice_name
				self._pending_voice = None
			if want_v and want_v != "System default" and want_v in voices:
				try:
					self._tts.setVoice(voices[want_v])
					self._voice_name = want_v
				except Exception:
					pass
			if not self._use_system_default:
				try:
					self._tts.setSpeechRate(float(self._rate_to_android(self._rate)))
					self._tts.setPitch(float(self._pitch_to_android(self._pitch)))
				except Exception:
					pass
		except Exception:
			pass

	def _enqueue(self, cmd, arg1=None, arg2=None, arg3=None, drop_pending_speech=False):
		with self._cond:
			if drop_pending_speech:
				self._speak_seq += 1
				self._queue = deque(item for item in self._queue if item[0] != "speak")
			seq = self._speak_seq
			self._queue.append((cmd, arg1, arg2, arg3, seq))
			self._cond.notify()

	def _worker_loop(self):
		while True:
			with self._cond:
				while not self._queue:
					self._cond.wait()
				cmd, arg1, arg2, arg3, seq = self._queue.popleft()

			try:
				if cmd == "speak":
					if seq != self._speak_seq and arg2:
						continue
					if _HAS_JAVA and self._tts is not None and not self._ready:
						deadline = time.monotonic() + 3.0
						with self._cond:
							while not self._ready and time.monotonic() < deadline:
								self._cond.wait(timeout=0.1)
					if seq != self._speak_seq and arg2:
						continue
					self._do_speak(arg1, arg2, arg3, seq)
				elif cmd == "silence":
					self._stop_bass()
					if self._tts is not None:
						try:
							self._tts.stop()
						except Exception:
							pass
				elif cmd == "rate":
					if self._tts is not None and self._ready:
						try:
							self._tts.setSpeechRate(float(self._rate_to_android(arg1)))
						except Exception:
							pass
				elif cmd == "pitch":
					if self._tts is not None and self._ready:
						try:
							self._tts.setPitch(float(self._pitch_to_android(arg1)))
						except Exception:
							pass
				elif cmd == "volume":
					with self._bass_lock:
						if self._bass_sound is not None:
							try:
								self._bass_sound.volume = arg1
							except Exception:
								pass
				elif cmd == "engine":
					self._init_native_tts(engine_pkg=str(arg1 or ""))
				elif cmd == "voice":
					if self._tts is not None and self._ready:
						if not arg1 or arg1 == "System default":
							try:
								def_v = self._tts.getDefaultVoice()
								if def_v is not None:
									self._tts.setVoice(def_v)
								else:
									Locale = _jclass("java.util.Locale")
									self._tts.setLanguage(Locale.getDefault())
								self._voice_name = "System default"
							except Exception:
								pass
						else:
							if not self._voices or arg1 not in self._voices:
								voices, locales = self._load_android_voices()
								with self._lock:
									self._voices = voices
									self._voice_names = list(voices.keys())
									self._voice_locales = locales
									self._voice_languages = ["All"] + sorted({tg for tg in locales.values() if tg})
							v_obj = self._voices.get(arg1)
							if v_obj is not None:
								try:
									self._tts.setVoice(v_obj)
									self._voice_name = arg1
								except Exception:
									pass
						# Re-apply rate/pitch after voice change (Google TTS may reset them)
						if not self._use_system_default:
							try:
								self._tts.setSpeechRate(float(self._rate_to_android(self._rate)))
								self._tts.setPitch(float(self._pitch_to_android(self._pitch)))
							except Exception:
								pass
			except Exception:
				pass

	def _bass_ready(self):
		try:
			from .. import sound_pool
			return sound_pool.bass.BASS_GetDevice() != -1
		except Exception:
			return False

	def _stop_bass(self):
		with self._bass_lock:
			snd = self._bass_sound
			self._bass_sound = None
		if snd is not None:
			try:
				snd.stop()
				snd.close()
			except Exception:
				pass

	@staticmethod
	def _convert_pcm_channels(pcm_bytes, src_channels, dst_channels, bits):
		if src_channels == dst_channels or not pcm_bytes:
			return pcm_bytes
		sample_bytes = 1 if bits == 8 else 2
		if src_channels == 1 and dst_channels == 2:
			out = bytearray(len(pcm_bytes) * 2)
			step = sample_bytes * 2
			for b in range(sample_bytes):
				out[b::step] = pcm_bytes[b::sample_bytes]
				out[b + sample_bytes::step] = pcm_bytes[b::sample_bytes]
			return bytes(out)
		if src_channels == 2 and dst_channels == 1:
			out = bytearray(len(pcm_bytes) // 2)
			step = sample_bytes * 2
			for b in range(sample_bytes):
				out[b::sample_bytes] = pcm_bytes[b::step]
			return bytes(out)
		return pcm_bytes

	def _play_pcm_via_bass(self, pcm_bytes, freq, channels, bits, interrupt, seq, pos3d=None):
		from .. import buffer, sound_pool
		if not pcm_bytes:
			return
		if not interrupt:
			while seq == self._speak_seq:
				with self._bass_lock:
					cur = self._bass_sound
				if cur is None or not cur.playing:
					break
				time.sleep(0.01)
			if seq != self._speak_seq:
				return

		self._stop_bass()
		if seq != self._speak_seq:
			return

		want_3d = bool(self._hrtf and pos3d is not None)
		if want_3d and not sound_pool.is_hrtf_ready():
			sound_pool.prewarm_hrtf_async(delay=0.0)
			use_3d = False
		else:
			use_3d = want_3d
		target_mono = True if use_3d else bool(self._mono)
		dst_channels = 1 if target_mono else 2
		pcm_out = self._convert_pcm_channels(pcm_bytes, int(channels), dst_channels, int(bits))

		snd = sound_pool.sound()
		buffer.hSound_poolbuffers.pop(snd.sound_token, None)
		snd.freq = int(freq)
		kwargs = {"eightbits": True} if bits == 8 else {}
		if use_3d:
			snd.stream("", draw=True, mono=True, ThreeD=True, **kwargs)
			try:
				sound_pool._initialize_hrtf().BASS_HRTF_SetLiveStreamMode(snd.handle, 0, 0)
			except Exception:
				pass
		else:
			snd.stream("", draw=True, mono=target_mono, **kwargs)
		buffer.hSound_poolbuffers.pop(snd.sound_token, None)
		if self._output_device != -1:
			try:
				sound_pool.bass.BASS_Init(int(self._output_device), 44100, 0, 0, None)
				sound_pool.bass.BASS_ChannelSetDevice(snd.handle, int(self._output_device))
			except Exception:
				pass
		snd.volume = self._volume
		snd.pitch = self._sound_pitch
		if not use_3d:
			snd.pan = self._pan

		fx_to_apply = None
		if self._fx == "zone":
			if pos3d is not None and pos3d[6].get("fx"):
				fx_to_apply = pos3d[6].get("fx")
			elif callable(self._zone_fx_provider):
				try:
					fx_to_apply = self._zone_fx_provider()
				except Exception:
					fx_to_apply = None
		elif self._fx:
			fx_to_apply = self._fx

		if use_3d and pos3d is not None:
			lx, ly, lz, sx, sy, sz, p3_kw = pos3d
			s3d_kw = {k: v for k, v in p3_kw.items() if k != "fx"}
			s3d_kw.setdefault("start_volume", self._volume)
			s3d_kw.setdefault("start_pan", self._pan)
			s3d_kw.setdefault("start_pitch", self._sound_pitch)
			snd.set3d(lx, ly, lz, sx, sy, sz, **s3d_kw)

		if fx_to_apply:
			for fx_item in (fx_to_apply if isinstance(fx_to_apply, (list, tuple)) else [fx_to_apply]):
				if fx_item and fx_item != "none":
					try:
						snd.setfx(fx_item)
					except Exception:
						pass

		snd.push(pcm_out)
		push_target = snd.dedata if snd.dedata else snd.handle
		sound_pool.bass.BASS_StreamPutData(push_target, b"", BASS_STREAMPROC_END)
		with self._bass_lock:
			if seq != self._speak_seq:
				try:
					snd.close()
				except Exception:
					pass
				return
			self._bass_sound = snd
		snd.play()

	def _synthesize_to_pcm(self, text, seq):
		if not _HAS_JAVA or self._tts is None or not self._ready or not self._synth_supported:
			return None
		tmp_dir = self._cache_dir or tempfile.gettempdir()
		uid = f"pyag_tts_{uuid.uuid4().hex}"
		wav_path = os.path.join(tmp_dir, f"{uid}.wav")
		done_ev = threading.Event()
		with self._utt_lock:
			self._utt_events[uid] = done_ev
		try:
			TextToSpeech = _jclass("android.speech.tts.TextToSpeech")
			rc = -1
			try:
				Bundle = _jclass("android.os.Bundle")
				JFile = _jclass("java.io.File")
				rc = int(self._tts.synthesizeToFile(str(text), Bundle(), JFile(wav_path), uid))
			except Exception:
				HashMap = _jclass("java.util.HashMap")
				Engine = _jclass("android.speech.tts.TextToSpeech$Engine")
				hmap = HashMap()
				hmap.put(Engine.KEY_PARAM_UTTERANCE_ID, uid)
				rc = int(self._tts.synthesizeToFile(str(text), hmap, wav_path))

			if rc != int(TextToSpeech.SUCCESS):
				return None

			deadline = time.monotonic() + 5.0
			while not done_ev.is_set() and time.monotonic() < deadline:
				if seq != self._speak_seq:
					return None
				done_ev.wait(timeout=0.05)

			if not os.path.isfile(wav_path) or os.path.getsize(wav_path) <= 44:
				return None

			with wave.open(wav_path, "rb") as wf:
				channels = wf.getnchannels()
				bits = wf.getsampwidth() * 8
				freq = wf.getframerate()
				pcm = wf.readframes(wf.getnframes())
			if not pcm:
				return None
			return pcm, freq, channels, bits
		except Exception:
			return None
		finally:
			with self._utt_lock:
				self._utt_events.pop(uid, None)
			try:
				if os.path.exists(wav_path):
					os.remove(wav_path)
			except OSError:
				pass

	def _speak_native(self, text, interrupt=False):
		if self._tts is None:
			return False
		try:
			TextToSpeech = _jclass("android.speech.tts.TextToSpeech")
			Engine = _jclass("android.speech.tts.TextToSpeech$Engine")
			AudioManager = _jclass("android.media.AudioManager")
			mode = TextToSpeech.QUEUE_FLUSH if interrupt else TextToSpeech.QUEUE_ADD
			if interrupt:
				try:
					self._tts.stop()
				except Exception:
					pass
			try:
				Bundle = _jclass("android.os.Bundle")
				params = Bundle()
				params.putInt(Engine.KEY_PARAM_STREAM, int(AudioManager.STREAM_MUSIC))
				params.putFloat(Engine.KEY_PARAM_VOLUME, float(self._volume / 100.0))
				self._tts.speak(str(text), mode, params, f"pyag_fb_{uuid.uuid4().hex}")
				return True
			except Exception:
				HashMap = _jclass("java.util.HashMap")
				hmap = HashMap()
				hmap.put(Engine.KEY_PARAM_STREAM, str(int(AudioManager.STREAM_MUSIC)))
				hmap.put(Engine.KEY_PARAM_VOLUME, str(float(self._volume / 100.0)))
				self._tts.speak(str(text), mode, hmap)
				return True
		except Exception:
			return False

	def _do_speak(self, text, interrupt, pos3d, seq):
		if _HAS_JAVA and self._tts is None:
			self._init_native_tts()
		if self._tts is not None and self._ready and self._bass_ready():
			if interrupt:
				self._stop_bass()
			synth = self._synthesize_to_pcm(text, seq)
			if synth is not None:
				pcm, freq, channels, bits = synth
				self._play_pcm_via_bass(pcm, freq, channels, bits, interrupt, seq, pos3d=pos3d)
				return
		if self._tts is not None:
			self._speak_native(text, interrupt)

	def is_active(self):
		return system.get_platform()["os"] == "android"

	def speak(self, text, interrupt=False):
		msg = str(text or "")
		if not msg:
			return
		try:
			import pygame
			if hasattr(pygame, "_android_bridge") and hasattr(pygame._android_bridge, "set_overlay_text"):
				pygame._android_bridge.set_overlay_text(msg, is_error=False)
		except Exception:
			pass
		# Non-blocking on main thread: only stop local BASS sound (<0.1ms); worker handles JNI tts.stop()
		if interrupt:
			self._stop_bass()
		self._enqueue("speak", msg, bool(interrupt), None, drop_pending_speech=bool(interrupt))

	def speak3d(self, text, lx, ly, lz, sx, sy, sz, interrupt=False, **kwargs):
		msg = str(text or "")
		if not msg:
			return
		if interrupt:
			self._stop_bass()
		self._enqueue("speak", msg, bool(interrupt), (lx, ly, lz, sx, sy, sz, kwargs), drop_pending_speech=bool(interrupt))

	def silence(self):
		self._stop_bass()
		self._enqueue("silence", drop_pending_speech=True)

	def get_sound(self):
		with self._bass_lock:
			return self._bass_sound

	def list_engines(self):
		with self._lock:
			return list(self._engines.keys())

	def get_engine(self):
		return self._engine_name

	def set_engine(self, value):
		target = str(value or "System default")
		with self._lock:
			if not self._ready:
				if target != "System default":
					self._engine_name = target
					self._pending_engine = target
				return True
			if target in self._engines:
				pkg = self._engines[target]
				lbl = target
			else:
				pkg = ""
				lbl = "System default"
				for k_lbl, k_pkg in self._engines.items():
					if k_pkg == target:
						lbl, pkg = k_lbl, k_pkg
						break
		if pkg == self._engine_pkg and lbl == self._engine_name:
			return True
		self._engine_name = lbl
		self._engine_pkg = pkg
		self._voice_name = "System default"
		self._voice_language = "All"
		self._enqueue("engine", pkg)
		return True

	def list_voice_languages(self):
		with self._lock:
			return list(self._voice_languages)

	def get_voice_language(self):
		return self._voice_language

	def set_voice_language(self, value):
		lang = str(value or "All")
		with self._lock:
			if not self._ready:
				self._voice_language = lang
				return True
			if lang not in self._voice_languages:
				lang = "All"
			self._voice_language = lang
			if self._voice_name != "System default" and lang != "All":
				if self._voice_locales.get(self._voice_name, "") != lang:
					self._voice_name = "System default"
		return True

	def get_use_system_default(self):
		return bool(self._use_system_default)

	def set_use_system_default(self, enabled):
		self._use_system_default = bool(enabled)
		if self._use_system_default:
			self._rate = 50
			self._pitch = 50
			self._voice_language = "All"
			self._voice_name = "System default"
			if self._engine_pkg:
				self.set_engine("System default")
			else:
				self._enqueue("voice", "System default")
				self._enqueue("rate", 50)
				self._enqueue("pitch", 50)
		return True

	def list_voices(self):
		with self._lock:
			if self._voice_language and self._voice_language != "All":
				filtered = [vn for vn in self._voice_names if self._voice_locales.get(vn, "") == self._voice_language]
			else:
				filtered = list(self._voice_names)
		return ["System default"] + filtered

	def get_voice(self):
		return self._voice_name or "System default"

	def set_voice(self, value):
		if not value or value == "System default":
			self._voice_name = "System default"
			self._pending_voice = None
			self._enqueue("voice", "System default")
			return True
		with self._lock:
			if not self._ready:
				self._voice_name = str(value)
				self._pending_voice = str(value)
				self._use_system_default = False
				return True
			if value not in self._voice_names:
				return False
		self._voice_name = value
		self._pending_voice = None
		self._use_system_default = False
		self._enqueue("voice", value)
		return True

	def get_rate(self): return self._rate
	def set_rate(self, value):
		val = max(0, min(100, int(round(value))))
		self._rate = val
		self._enqueue("rate", val)
		return True

	def get_pitch(self): return self._pitch
	def set_pitch(self, value):
		val = max(0, min(100, int(round(value))))
		self._pitch = val
		self._enqueue("pitch", val)
		return True

	def get_volume(self): return self._volume
	def set_volume(self, value):
		val = max(0, min(100, int(round(value))))
		self._volume = val
		self._enqueue("volume", val)
		return True

	def get_pan(self): return self._pan
	def set_pan(self, value):
		val = max(-100.0, min(100.0, float(value)))
		self._pan = val
		with self._bass_lock:
			if self._bass_sound is not None:
				try:
					self._bass_sound.pan = val
				except Exception:
					pass
		return True

	def get_sound_pitch(self): return self._sound_pitch
	def set_sound_pitch(self, value):
		val = max(10.0, min(400.0, float(value)))
		self._sound_pitch = val
		with self._bass_lock:
			if self._bass_sound is not None:
				try:
					self._bass_sound.pitch = val
				except Exception:
					pass
		return True

	def get_output_device(self): return self._output_device
	def set_output_device(self, value):
		dev = int(value) if value is not None else -1
		self._output_device = dev
		with self._bass_lock:
			snd = self._bass_sound
		if snd is not None and snd.handle and dev != -1:
			try:
				from .. import sound_pool
				sound_pool.bass.BASS_Init(dev, 44100, 0, 0, None)
				sound_pool.bass.BASS_ChannelSetDevice(snd.handle, dev)
			except Exception:
				pass
		return True

	def get_mono(self): return self._mono
	def set_mono(self, value): self._mono = bool(value); return True
	def get_hrtf(self): return self._hrtf
	def set_hrtf(self, value): self._hrtf = bool(value); return True
	def get_fx(self): return self._fx
	def set_fx(self, value): self._fx = None if value in (None, "", "none") else value; return True
	def set_zone_fx_provider(self, provider): self._zone_fx_provider = provider; return True
	def get_auto_pause(self): return self._auto_pause
	def set_auto_pause(self, enabled): self._auto_pause = bool(enabled); return True


class AndroidScreenReader(Provider):
	"""Routes speech directly to Android TalkBack / Jieshuo via UI-thread AccessibilityEvent."""
	name = "Screen Reader"
	aliases = ("mobile_sr", "screen_reader")
	priority = 102
	is_system_output = True

	def _get_activity(self):
		if not _HAS_JAVA:
			return None
		try:
			from ..pygame_shim import _android_bridge
			return _android_bridge.get_activity()
		except Exception:
			return None

	def is_active(self):
		return system.get_platform()["os"] == "android" and _HAS_JAVA and self._get_activity() is not None

	def speak(self, text, interrupt=False):
		msg = str(text or "")
		if not msg:
			return
		act = self._get_activity()
		if act is None:
			return
		try:
			from ..pygame_shim import _android_bridge
			Context = _jclass("android.content.Context")
			AccessibilityEvent = _jclass("android.view.accessibility.AccessibilityEvent")
			view = _android_bridge.get_view()

			def _announce():
				try:
					am = act.getSystemService(Context.ACCESSIBILITY_SERVICE)
					if am is not None and am.isEnabled():
						if interrupt:
							try:
								am.interrupt()
							except Exception:
								pass
						ev = AccessibilityEvent.obtain(AccessibilityEvent.TYPE_ANNOUNCEMENT)
						ev.getText().add(msg)
						ev.setPackageName(act.getPackageName())
						am.sendAccessibilityEvent(ev)
						return
				except Exception:
					pass
				if view is not None and hasattr(view, "announceForAccessibility"):
					try:
						view.announceForAccessibility(msg)
					except Exception:
						pass

			_android_bridge._run_on_ui_sync(_announce, timeout=0.5)
		except Exception:
			pass

	def silence(self):
		act = self._get_activity()
		if act is not None and _HAS_JAVA:
			try:
				Context = _jclass("android.content.Context")
				am = act.getSystemService(Context.ACCESSIBILITY_SERVICE)
				if am is not None and am.isEnabled():
					am.interrupt()
			except Exception:
				pass


def create_providers():
	# AndroidTTS (priority 100) wins over AndroidScreenReader (priority 102) in Auto, matching reference accessible_output2
	return [AndroidTTS(), AndroidScreenReader()]
