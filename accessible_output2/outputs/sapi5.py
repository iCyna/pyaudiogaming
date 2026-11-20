from __future__ import absolute_import
from array import array
from collections import OrderedDict, deque
import threading
import time
from ..com import load_com
from .base import Output, OutputError
import pywintypes
import logging
from xml.sax.saxutils import escape
log = logging.getLogger(__name__)

SVSFDefault = 0
SVSFlagsAsync = 1
SVSFPurgeBeforeSpeak = 2
SVSFIsFilename = 4
SVSFIsXML = 8
SVSFIsNotXML = 16
SVSFPersistXML = 32
BASS_STREAMPROC_END = 0x80000000


class SAPI5(Output):
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
	name = "sapi5"
	priority = 101
	system_output = True

	def __init__(self):
		self._voices = None
		self._voice_names = []
		self._voice_name = ""
		self._pitch = 0
		self._sound_pitch = 100.0
		self._pan = 0.0
		self._mono = False
		self._hrtf = False
		self._fx = None
		self._zone_fx_provider = None
		self._output_device = -1
		self._rate = 0
		self._com_rate = 0
		self._volume = 100
		self._voice_xml_mode = {}
		self._cond = threading.Condition()
		self._queue = deque()
		self._ready = threading.Event()
		self._init_error = None
		self._active = False
		self._speak_seq = 0
		self._bass_lock = threading.Lock()
		self._bass_sound = None
		self._mem_stream = None
		self.object = None

		self._worker = threading.Thread(target=self._worker_loop, daemon=True)
		self._worker.start()
		self._ready.wait(timeout=5.0)
		if self._init_error is not None:
			raise OutputError(f"Cannot initialize SAPI5: {self._init_error}") from self._init_error
		if not self._active:
			raise OutputError("Cannot initialize SAPI5: initialization timed out")

	def _worker_loop(self):
		pythoncom = None
		try:
			import pythoncom as _pythoncom
			pythoncom = _pythoncom
			pythoncom.CoInitialize()
		except Exception:
			pythoncom = None

		try:
			self.object = load_com("SAPI.SPVoice")
			self._rate = int(self.object.Rate)
			self._com_rate = self._rate
			self._volume = int(self.object.Volume)
			try:
				self._voice_name = self.object.Voice.GetDescription()
			except Exception:
				self._voice_name = ""
			self._voices = self._available_voices()
			self._voice_names = list(self._voices.keys())
			self._active = True
		except (pywintypes.com_error, AttributeError) as error:
			self._init_error = error
			self._ready.set()
			if pythoncom is not None:
				try:
					pythoncom.CoUninitialize()
				except Exception:
					pass
			return

		self._ready.set()

		while True:
			with self._cond:
				while not self._queue:
					self._cond.wait()
				cmd, arg1, arg2, arg3, seq = self._queue.popleft()

			try:
				if cmd == "speak":
					if seq != self._speak_seq and arg2:
						continue
					self._do_speak(arg1, arg2, arg3, seq)
				elif cmd == "silence":
					self._stop_bass()
					try:
						self.object.Speak("", SVSFlagsAsync | SVSFPurgeBeforeSpeak)
					except Exception:
						pass
				elif cmd == "rate":
					try:
						self.object.Rate = arg1
					except pywintypes.com_error:
						self.object.Rate = max(-10, min(10, arg1))
					self._com_rate = int(self.object.Rate)
				elif cmd == "volume":
					self.object.Volume = arg1
					with self._bass_lock:
						if self._bass_sound is not None:
							try:
								self._bass_sound.volume = arg1
							except Exception:
								pass
				elif cmd == "voice":
					if self._voices is None or arg1 not in self._voices:
						self._voices = self._available_voices()
						self._voice_names = list(self._voices.keys())
					if arg1 in self._voices:
						self.object.Voice = self._voices[arg1]
						self._voice_name = arg1
			except Exception as error:
				log.debug("SAPI5 worker error (%s): %s", cmd, error)

	def _enqueue(self, cmd, arg1=None, arg2=None, arg3=None, drop_pending_speech=False):
		with self._cond:
			if drop_pending_speech:
				self._speak_seq += 1
				self._queue = deque(item for item in self._queue if item[0] != "speak")
			seq = self._speak_seq
			self._queue.append((cmd, arg1, arg2, arg3, seq))
			self._cond.notify()

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

	def _available_voices(self):
		voices = OrderedDict()
		self.voice_error = None
		try:
			tokens = self.object.GetVoices()
			for i in range(tokens.Count):
				token = tokens.Item(i)
				voices[token.GetDescription()] = token
		except pywintypes.com_error as error:
			# Some installed engines break SAPI's combined enumerator.
			self.voice_error = str(error)
			log.debug("SAPI voice enumeration failed: %s", error)
			import winreg
			path = r"SOFTWARE\Microsoft\Speech\Voices\Tokens"
			for hive, label in ((winreg.HKEY_CURRENT_USER, "HKEY_CURRENT_USER"), (winreg.HKEY_LOCAL_MACHINE, "HKEY_LOCAL_MACHINE")):
				try:
					with winreg.OpenKey(hive, path) as root:
						for i in range(winreg.QueryInfoKey(root)[0]):
							try:
								token = load_com("SAPI.SpObjectToken")
								token.SetId(label + "\\" + path + "\\" + winreg.EnumKey(root, i))
								voices[token.GetDescription()] = token
							except (pywintypes.com_error, OSError):
								continue
				except OSError:
					continue
		if not voices and self.object is not None:
			token = self.object.Voice
			voices[token.GetDescription()] = token
		return voices

	def list_voices(self):
		return list(self._voice_names)

	def get_voice(self):
		return self._voice_name

	def set_voice(self, value):
		log.debug("Setting SAPI5 voice to \"%s\"" % value)
		if value not in self._voice_names:
			return
		self._voice_name = value
		self._enqueue("voice", value)

	def get_pitch(self):
		return self._pitch

	def set_pitch(self, value):
		val = max(self.min_pitch, min(self.max_pitch, int(round(value))))
		log.debug("Setting pitch to %d" % val)
		self._pitch = val

	def get_rate(self):
		return self._rate

	def set_rate(self, value):
		val = max(self.min_rate, min(self.max_rate, int(round(value))))
		log.debug("Setting rate to %d" % val)
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

	def _build_sapi_xml(self, text, pitch, extra_rate):
		inner = '<pitch absmiddle="%d">%s</pitch>' % (pitch, escape(text))
		if extra_rate > 0:
			return '<rate speed="%d">%s</rate>' % (extra_rate, inner)
		return inner

	def _build_ssml(self, text, pitch, extra_rate):
		attrs = []
		if pitch != 0:
			attrs.append('pitch="%+d%%"' % (pitch * 5))
		if extra_rate > 0:
			attrs.append('rate="%+d%%"' % (extra_rate * 10))
		attr_str = (" " + " ".join(attrs)) if attrs else ""
		return (
			'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
			'<prosody%s>%s</prosody></speak>' % (attr_str, escape(text))
		)

	def _speak_with_xml_fallback(self, text, flags_base):
		pitch = max(self.min_pitch, min(self.max_pitch, int(round(self._pitch))))
		extra_rate = max(0, self._rate - self._com_rate)

		if pitch == 0 and extra_rate == 0:
			self.object.Speak(text, flags_base | SVSFIsNotXML)
			return

		voice_key = self._voice_name or "_default"
		mode = self._voice_xml_mode.get(voice_key, "sapi")

		if mode == "sapi":
			try:
				xml_text = self._build_sapi_xml(text, pitch, extra_rate)
				self.object.Speak(xml_text, flags_base | SVSFIsXML)
				return
			except pywintypes.com_error:
				mode = "ssml"
				self._voice_xml_mode[voice_key] = mode

		if mode == "ssml":
			try:
				ssml_text = self._build_ssml(text, pitch, extra_rate)
				self.object.Speak(ssml_text, flags_base | SVSFIsXML)
				return
			except pywintypes.com_error:
				self._voice_xml_mode[voice_key] = "plain"

		self.object.Speak(text, flags_base | SVSFIsNotXML)

	def _do_speak(self, text, interrupt, pos3d, seq):
		if self._bass_ready():
			if interrupt:
				self._stop_bass()
			mem = load_com("SAPI.SpMemoryStream")
			self.object.AudioOutputStream = mem
			self._speak_with_xml_fallback(text, SVSFDefault)
			pcm = bytes(mem.GetData())
			wf = mem.Format.GetWaveFormatEx()
			self._play_pcm_via_bass(
				pcm,
				wf.SamplesPerSec,
				wf.Channels,
				wf.BitsPerSample,
				interrupt,
				seq,
				pos3d=pos3d,
			)
			return

		try:
			if self.object.AudioOutputStream is not None:
				self.object.AudioOutputStream = None
		except Exception:
			pass
		purge = SVSFPurgeBeforeSpeak if interrupt else 0
		self._speak_with_xml_fallback(text, SVSFlagsAsync | purge)

	def speak(self, text, interrupt=False, pos3d=None):
		if interrupt:
			self._stop_bass()
		self._enqueue("speak", str(text), bool(interrupt), pos3d, drop_pending_speech=bool(interrupt))

	def silence(self):
		self._stop_bass()
		self._enqueue("silence", drop_pending_speech=True)

	def is_active(self):
		return self._active and self.object is not None


output_class = SAPI5
