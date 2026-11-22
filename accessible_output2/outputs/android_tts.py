# -*- coding: utf-8 -*-
"""Android/iOS TTS output modeled after SAPI5: BASS PCM playback (volume/pan/mono/HRTF/FX) with Media-stream native fallback."""
from array import array
from collections import OrderedDict, deque
import logging
import os
import tempfile
import threading
import time
import uuid
import wave

from .base import Output
from pyaudiogaming import system

log = logging.getLogger(__name__)

BASS_STREAMPROC_END = 0x80000000

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
	"""Android/iOS speech output matching SAPI5 capabilities and BASS routing."""
	has_volume = True
	has_rate = True
	has_pitch = True
	has_pan = True
	has_mono = True
	has_hrtf = True
	has_fx = True
	min_pitch = -10
	max_pitch = 10
	min_rate = -10
	max_rate = 30
	min_volume = 0
	max_volume = 100
	min_pan = -100
	max_pan = 100
	name = "Android_TTS"
	priority = 100
	system_output = True

	def __init__(self):
		super().__init__()
		self._tts = None
		self._ready = False
		self._lock = threading.Lock()
		self._cond = threading.Condition()
		self._queue = deque()
		self._speak_seq = 0
		self._voices = OrderedDict()
		self._voice_names = []
		self._voice_name = ""
		self._rate = 0
		self._pitch = 0
		self._volume = 100
		self._sound_pitch = 100.0
		self._pan = 0.0
		self._mono = False
		self._hrtf = False
		self._fx = None
		self._zone_fx_provider = None
		self._output_device = -1
		self._bass_lock = threading.Lock()
		self._bass_sound = None
		self._listener = None
		self._utt_listener = None
		self._utt_events = {}
		self._utt_lock = threading.Lock()
		self._cache_dir = None
		self._synth_supported = True

		self._init_native_tts()
		self._worker = threading.Thread(target=self._worker_loop, name="AndroidTTSWorker", daemon=True)
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
			platform = Python.getPlatform()
			if hasattr(platform, "getApplication"):
				return platform.getApplication()
		except Exception:
			pass
		return None

	def _rate_to_android(self, val):
		val = float(val)
		if val >= 0:
			return max(0.25, min(4.0, 1.0 + val * 0.1))
		return max(0.25, min(4.0, 1.0 + val * 0.05))

	def _pitch_to_android(self, val):
		return max(0.25, min(2.0, 2.0 ** (float(val) / 10.0)))

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
		except Exception as exc:
			log.debug("Android_TTS setAudioAttributes skipped: %s", exc)

	def _load_android_voices(self):
		voices = OrderedDict()
		if not _HAS_JAVA or self._tts is None:
			return voices
		try:
			vset = self._tts.getVoices()
			if vset is not None:
				for v in vset.toArray():
					try:
						vname = str(v.getName())
						if vname:
							voices[vname] = v
					except Exception:
						continue
		except Exception as exc:
			log.debug("Android_TTS getVoices failed: %s", exc)
		try:
			cur = self._tts.getVoice()
			if cur is not None:
				cur_name = str(cur.getName())
				self._voice_name = cur_name
				if cur_name and cur_name not in voices:
					voices[cur_name] = cur
		except Exception:
			pass
		return voices

	def _init_native_tts(self):
		if not _HAS_JAVA:
			return
		ctx = self._get_context()
		if ctx is None:
			return
		try:
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
						try:
							self_ref._tts.setSpeechRate(float(self_ref._rate_to_android(self_ref._rate)))
							self_ref._tts.setPitch(float(self_ref._pitch_to_android(self_ref._pitch)))
						except Exception:
							pass
						voices = self_ref._load_android_voices()
						with self_ref._lock:
							self_ref._voices = voices
							self_ref._voice_names = list(voices.keys())
							self_ref._ready = True
						with self_ref._cond:
							self_ref._cond.notify_all()

			self._utt_listener = _UttListener()
			self._listener = _InitListener()
			self._tts = TextToSpeech(ctx, self._listener)
		except Exception as exc:
			print(f"[Android_TTS] Native TextToSpeech init failed: {exc}")
			self._tts = None

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
					# Wait briefly if Android TTS engine is still initializing
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
				elif cmd == "voice":
					if self._tts is not None and self._ready:
						if not self._voices or arg1 not in self._voices:
							voices = self._load_android_voices()
							with self._lock:
								self._voices = voices
								self._voice_names = list(voices.keys())
						v_obj = self._voices.get(arg1)
						if v_obj is not None:
							try:
								self._tts.setVoice(v_obj)
								self._voice_name = arg1
							except Exception:
								pass
			except Exception as error:
				log.debug("Android_TTS worker error (%s): %s", cmd, error)

	def _bass_ready(self):
		try:
			from ... import sound_pool
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

	@staticmethod
	def _pcm_to_float32(pcm_bytes, bits):
		if not pcm_bytes:
			return pcm_bytes
		if bits == 8:
			return array("f", ((b - 128) / 128.0 for b in pcm_bytes)).tobytes()
		samples = array("h")
		samples.frombytes(pcm_bytes)
		return array("f", (s / 32768.0 for s in samples)).tobytes()

	def _play_pcm_via_bass(self, pcm_bytes, freq, channels, bits, interrupt, seq, pos3d=None):
		from ... import buffer, sound_pool
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

		use_3d = bool(self._hrtf and pos3d is not None)
		target_mono = True if use_3d else bool(self._mono)
		dst_channels = 1 if target_mono else 2
		pcm_out = self._convert_pcm_channels(pcm_bytes, int(channels), dst_channels, int(bits))

		snd = sound_pool.sound()
		buffer.hSound_poolbuffers.pop(snd.sound_token, None)
		snd.freq = int(freq)
		kwargs = {"eightbits": True} if (bits == 8 and not use_3d) else {}
		if use_3d:
			pcm_out = self._pcm_to_float32(pcm_out, int(bits))
			snd.stream("", draw=True, mono=True, ThreeD=True, **kwargs)
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
		"""Synthesize Android TTS to a temporary WAV file and read raw PCM (like SAPI5 SpMemoryStream)."""
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
				params = Bundle()
				rc = int(self._tts.synthesizeToFile(str(text), params, JFile(wav_path), uid))
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
		except Exception as exc:
			log.debug("Android_TTS synthesizeToFile failed: %s", exc)
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

		if self._tts is not None and self._speak_native(text, interrupt):
			return

		if _plyer_tts is not None:
			try:
				_plyer_tts.speak(text)
			except Exception:
				pass

	def list_voices(self):
		return list(self._voice_names)

	def get_voice(self):
		return self._voice_name

	def set_voice(self, value):
		if value not in self._voice_names:
			return
		self._voice_name = value
		self._enqueue("voice", value)

	def get_pitch(self):
		return self._pitch

	def set_pitch(self, value):
		val = max(self.min_pitch, min(self.max_pitch, int(round(value))))
		self._pitch = val
		self._enqueue("pitch", val)

	def get_rate(self):
		return self._rate

	def set_rate(self, value):
		val = max(self.min_rate, min(self.max_rate, int(round(value))))
		self._rate = val
		self._enqueue("rate", val)

	def get_volume(self):
		return self._volume

	def set_volume(self, value):
		val = max(self.min_volume, min(self.max_volume, int(round(value))))
		self._volume = val
		self._enqueue("volume", val)

	def get_pan(self):
		return self._pan

	def set_pan(self, value):
		val = max(self.min_pan, min(self.max_pan, float(value)))
		self._pan = val
		with self._bass_lock:
			if self._bass_sound is not None:
				try:
					self._bass_sound.pan = val
				except Exception:
					pass

	def get_sound_pitch(self):
		return self._sound_pitch

	def set_sound_pitch(self, value):
		val = max(10.0, min(400.0, float(value)))
		self._sound_pitch = val
		with self._bass_lock:
			if self._bass_sound is not None:
				try:
					self._bass_sound.pitch = val
				except Exception:
					pass

	def get_output_device(self):
		return self._output_device

	def set_output_device(self, device):
		dev = int(device) if device is not None else -1
		self._output_device = dev
		with self._bass_lock:
			snd = self._bass_sound
		if snd is not None and snd.handle and dev != -1:
			try:
				from ... import sound_pool
				sound_pool.bass.BASS_Init(dev, 44100, 0, 0, None)
				sound_pool.bass.BASS_ChannelSetDevice(snd.handle, dev)
			except Exception:
				pass

	def get_sound(self):
		with self._bass_lock:
			return self._bass_sound

	def get_mono(self):
		return self._mono

	def set_mono(self, value):
		self._mono = bool(value)

	def get_hrtf(self):
		return self._hrtf

	def set_hrtf(self, value):
		self._hrtf = bool(value)

	def get_fx(self):
		return self._fx

	def set_fx(self, value):
		self._fx = None if value in (None, "", "none") else value

	def set_zone_fx_provider(self, provider):
		self._zone_fx_provider = provider

	def list_fx(self):
		try:
			from ...sound_fx import Basic
			fx = Basic()
			return list(dict.fromkeys(list(fx.fxs.keys()) + list(fx.filters.keys())))
		except Exception:
			return []

	def is_active(self):
		os_info = system.get_platform()["os"]
		return os_info in ("android", "ios")

	def speak(self, text, interrupt=False, pos3d=None):
		msg = str(text)
		if not msg:
			return
		try:
			import pygame
			if hasattr(pygame, "_android_bridge") and hasattr(pygame._android_bridge, "set_overlay_text"):
				pygame._android_bridge.set_overlay_text(msg, is_error=False)
		except Exception:
			pass
		if interrupt:
			self._stop_bass()
		self._enqueue("speak", msg, bool(interrupt), pos3d, drop_pending_speech=bool(interrupt))

	def silence(self):
		self._stop_bass()
		self._enqueue("silence", drop_pending_speech=True)


output_class = Android_TTS
