# -*- coding: utf-8 -*-
#sound system multifunctional
# copyright 2026 belong ihcyna (Labubu)<phucnggo29@gmail.com>.
#some of idea from other elsewhere

import math
import os
import ctypes
from . import system, sound_lib, utils, buffer
from .sound_lib.instrument import SoundFont, MIDIStream, MIDIFileStream
from .sound_lib.recording import *
from .sound_lib.encoder import *
from .sound_fx import *
from .sound_lib.external import pybassvst, pybassmix as bassmix
from .sound_lib.external import pybass_fx

_hrtf = None
_hrtf_sample_rate = None


def _initialize_hrtf(sample_rate=None):
	"""Load the native HRTF add-on only when spatial audio is requested."""
	global _hrtf, _hrtf_sample_rate
	if _hrtf is None:
		from .sound_lib.external import pybass_hrtf
		_hrtf = pybass_hrtf
	if sample_rate is None:
		device = buffer.hAudiobuffers.get("output")
		sample_rate = getattr(device, "frequency", 44100)
	if _hrtf_sample_rate is None:
		# Resolve bundled dependencies explicitly instead of relying on the cwd.
		if not _hrtf.BASS_HRTF_InitEx(int(sample_rate), os.fsencode(system.get_path("bass")), os.fsencode(system.get_path("phonon")), None, 0x040500):
			raise RuntimeError("BASS_HRTF_Init failed; check bass_hrtf and phonon libraries")
		_hrtf_sample_rate = int(sample_rate)
	elif int(sample_rate) != _hrtf_sample_rate:
		raise RuntimeError("HRTF is already initialized with a different sample rate")
	return _hrtf


def set_hrtf_distance_model(min_dist=1.0, max_dist=50.0, rolloff=0.12, blend_step=0.25):
	"""Cấu hình toàn cục độ mượt khoảng cách và độ tách góc HRTF."""
	hrtf = _initialize_hrtf()
	hrtf.BASS_HRTF_SetDistanceModel(float(min_dist), float(max_dist), float(rolloff), float(blend_step))


def output(period=10, bbuffer=500, ThreeD=False, sample_rate=44100):
	# BASS and HRTF must use the same output sample rate.
	sound_lib.main.BASS_SetConfig(sound_lib.main.BASS_CONFIG_UPDATEPERIOD, period)
	sound_lib.main.BASS_SetConfig(sound_lib.main.BASS_CONFIG_BUFFER, bbuffer)
	o = sound_lib.output.Output(frequency=sample_rate)
	buffer.hAudiobuffers["output"] = o
	buffer.hfxbuffers["basic"] = Basic()
	if ThreeD:
		_initialize_hrtf(sample_rate)
	return o

def input():
	# initialize input device
	i = sound_lib.input.Input()
	buffer.hAudiobuffers["input"] = i
	return i


class SoundBase:
	def __init__(self):
		self.handle = None
		self.dedata = None
		self.active_fx_handles = {}
		self.mono = False
		self.freq = 44100
		self.paused = False
		self._pitch_shift_fx = None
		self._tone_semitones = 0.0

		# Trạng thái quản lý 3D & HRTF chung cho MỌI đối tượng (Stream, Sample, MIDI, Mixer, VST)
		self._hrtf_stream = False
		self._hrtf_dsp = 0
		self._3d = None

		# Cho phép user tinh chỉnh bù trừ thêm Pan / Volume / Pitch chồng lên kết quả 3D
		self.user_volume_offset = 0.0  # Cộng/trừ thêm % âm lượng (VD: +10 hoặc -15)
		self.user_pan_offset = 0.0     # Cộng/trừ thêm % pan trái/phải (-100 đến +100)
		self.user_pitch_offset = 0.0   # Cộng/trừ thêm % pitch

	def _get_raw_channel_handle(self):
		if not self.handle:
			return 0
		raw = getattr(self.handle, "handle", self.handle)
		if hasattr(raw, "value"):
			return int(raw.value)
		try:
			return int(raw)
		except Exception:
			return 0

	# --- HỆ THỐNG GẮN DSP HRTF TRỰC TIẾP (SIÊU NHẸ, DÙNG CHO MỌI ĐỐI TƯỢNG) ---

	def attach_hrtf_dsp(self, priority=0):
		"""Gắn HRTF bằng DSP trực tiếp lên kênh hiện tại (Stream, Sample, MIDI, Mixer, VST)
		mà KHÔNG cần tạo stream mới tốn kém."""
		if self._hrtf_stream:
			return True
		if self._hrtf_dsp:
			return True
		raw = self._get_raw_channel_handle()
		if not raw:
			return False
		hrtf = _initialize_hrtf()
		dsp = hrtf.BASS_HRTF_AttachDSP(raw, int(priority))
		if dsp:
			self._hrtf_dsp = dsp
			return True
		return False

	def detach_hrtf_dsp(self):
		"""Gỡ DSP HRTF khỏi kênh để trở về âm thanh 2D nguyên bản."""
		if not self._hrtf_dsp:
			return False
		raw = self._get_raw_channel_handle()
		if _hrtf and raw:
			_hrtf.BASS_HRTF_DetachDSP(raw)
		self._hrtf_dsp = 0
		return True

	def set_hrtf_enabled(self, enabled=True):
		"""Bật/Tắt nhanh hiệu ứng HRTF mà không cần tháo DSP."""
		raw = self._get_raw_channel_handle()
		if not raw or not _hrtf:
			return False
		return bool(_hrtf.BASS_HRTF_SetEnabled(raw, 1 if enabled else 0))

	def enable_physical_filter(self, enabled=False):
		"""Bật hoặc tắt riêng bộ lọc vật lý (EQ không khí & tường chắn).
		Mặc định là False (giữ nguyên âm thanh HRTF nguyên thủy nhất)."""
		raw = self._get_raw_channel_handle()
		if not raw or not _hrtf:
			return False
		return bool(_hrtf.BASS_HRTF_EnablePhysicalFilter(raw, 1 if enabled else 0))

	def set_physical_3d(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	                    occlusion=0.0, air_absorption=1.0, rotation=0.0,
	                    low_trans=None, mid_trans=None, high_trans=None):
		"""Hàm chuyên biệt để kích hoạt và điều chỉnh bộ lọc vật lý (xuyên tường & hấp thụ không khí)."""
		if not self._hrtf_stream and not self._hrtf_dsp:
			if not self.attach_hrtf_dsp():
				self._attach_hrtf()
		raw = self._get_raw_channel_handle()
		if not raw:
			return False
		hrtf = _initialize_hrtf()

		dx = float(source_x - listener_x)
		dy = float(source_y - listener_y)
		dz = float(source_z - listener_z)
		if abs(rotation) > 0.001:
			rad = math.radians(rotation)
			cos_a = math.cos(rad)
			sin_a = math.sin(rad)
			rx = cos_a * dx - sin_a * dy
			ry = sin_a * dx + cos_a * dy
			dx, dy = rx, ry

		if low_trans is not None and mid_trans is not None and high_trans is not None:
			hrtf.BASS_HRTF_SetTransmissionBands(raw, float(low_trans), float(mid_trans), float(high_trans))

		return bool(hrtf.BASS_HRTF_SetPhysicalParams(raw, dx, dy, dz, float(occlusion), float(air_absorption)))

	def setPaused(self, p):
		if self.paused == p:
			return
		if not self.playing and p:
			return
		self.paused = p
		if p:
			self.handle.pause()
		else:
			self.handle.play()

	def fadeout(self, fadetime, value=0, type="volume"):
		if self.handle and self.handle.is_playing:
			self.handle.slide_attribute(type, value, fadetime)

	def fadein(self, fadetime, value=100, type="volume"):
		if self.handle and self.handle.is_playing:
			self.handle.slide_attribute(type, float(value)/100, fadetime)

	def setfx(self, fx_key, priority=0):
		"""
		Applies a professional FX or hardware filter preset from the Basic studio engine.
		Automatically safely replaces and manages internal BASS allocation layers.
		"""
		if not self.handle:
			return False
			
		fx_engine = buffer.hfxbuffers.get("basic")
		if not fx_engine:
			return False

		is_filter = False
		target = fx_engine.fxs.get(fx_key)
		if not target:
			target = fx_engine.filters.get(fx_key)
			is_filter = True
		if not target:
			return False

		if fx_key in self.active_fx_handles:
			try:
				self.handle.remove_fx(self.active_fx_handles[fx_key])
			except Exception:
				pass

		raw_native_handle = getattr(self.handle, "handle", None)
		if raw_native_handle is None:
			return False

		try:
			fx_alloc_handle = self.handle.set_fx(target["name"], priority)
			params_payload = target["param"]()
			self.handle.set_fx_setparam(fx_alloc_handle, params_payload)
			self.active_fx_handles[fx_key] = fx_alloc_handle
			return True
		except Exception as ex:
			print(ex)
			return False

	def remove_all_fx(self):
		"""Safely purges the processing stack channel pipeline architecture."""
		if not self.handle:
			return
		for fx_key, fx_handle in list(self.active_fx_handles.items()):
			try:
				self.handle.remove_fx(fx_handle)
			except Exception:
				pass
		self.active_fx_handles.clear()

	def get_data(self, frame_size=512, data_type="raw"):
		handle = self.dedata if self.dedata else self.handle
		if not handle:
			return None
		if data_type == "raw":
			return handle.get_data(length=frame_size * 2)

		bytes_per_sample = 4 if "32" in data_type else 2
		total_bytes = frame_size * bytes_per_sample
		flag = 0x40000000 if "32" in data_type else 0
		raw_buffer = handle.get_data(length=total_bytes | flag)
		
		if not raw_buffer: 
			return None

		if data_type == "float32":
			return ctypes.cast(raw_buffer, ctypes.POINTER(ctypes.c_float))[:frame_size]
		elif data_type == "int16":
			return ctypes.cast(raw_buffer, ctypes.POINTER(ctypes.c_int16))
		return raw_buffer

	def get_length(self):
		handle = self.dedata if self.dedata else self.handle
		if not handle:
			return -1
		return int(handle.length_in_seconds() * 1000)

	@property
	def volume(self):
		if not self.handle:
			return False
		return self.handle.get_volume() * 100

	@volume.setter
	def volume(self, value):
		if not self.handle:
			return False
		v = max(0.0, min(100.0, float(value)))
		self.handle.set_volume(v / 100.0)

	def _ensure_pitch_fx(self):
		if not self.handle:
			return False
		if self._pitch_shift_fx is not None:
			return True

		c_handle = self._get_raw_channel_handle()
		if not c_handle:
			return False
		try:
			# BASS_FX_BFX_PITCHSHIFT = 0x10015
			self._pitch_shift_fx = self.handle.set_fx(0x10015, priority=0)
			return True
		except Exception:
			self._pitch_shift_fx = None
			return False

	def set_tone(self, semitones, fft_size=2048, osamp=8):
		self._tone_semitones = float(semitones)
		if not self._ensure_pitch_fx():
			return False

		try:
			params = BASS_BFX_PITCHSHIFT()
			params.fPitchShift = 1.0
			params.fSemitones = float(semitones)
			params.lFFTsize = int(fft_size)
			params.lOsamp = int(osamp)
			params.lChannel = -1  # BASS_BFX_CHANALL

			self.handle.set_fx_setparam(self._pitch_shift_fx, params)
			return True
		except Exception as ex:
			print(f"[PitchShift Error]: {ex}")
			return False

	def get_tone(self):
		return self._tone_semitones

	@property
	def pitch(self):
		if not self.handle:
			return False
		return (self.handle.get_frequency() / self.freq) * 100

	@pitch.setter
	def pitch(self, value):
		if not self.handle:
			return False
		self.handle.set_frequency((float(value) / 100.0) * self.freq)

	@property
	def pan(self):
		if not self.handle:
			return False
		return self.handle.get_pan() * 100

	@pan.setter
	def pan(self, value):
		if not self.handle:
			return False
		p = max(-100.0, min(100.0, float(value)))
		self.handle.set_pan(p / 100.0)

	@property
	def playing(self):
		if self.handle is None:
			return False
		try:
			return self.handle.is_playing
		except Exception:
			return False

	@property
	def stopped(self):
		if not self.handle:
			return True
		return self.handle.is_stopped

	@property
	def stalled(self):
		if not self.handle:
			return False
		return self.handle.is_stalled

	def lock(self):
		if self.handle:
			return self.handle.lock()
		return False

	def unlock(self):
		if self.handle:
			return self.handle.unlock()
		return False

	def link(self, other):
		if not self.handle or not other:
			return False		
		if hasattr(other, "handle") and other.handle:
			target = other.handle.handle
		elif hasattr(other, "handle"):
			target = other.handle
		else:
			target = other
		try:
			self.handle.set_link(target)
			return True
		except Exception:
			return False

	def unlink(self, other):
		if not self.handle or not other:
			return False
		if hasattr(other, "handle") and other.handle:
			target_handle = other.handle.handle
		elif hasattr(other, "handle"):
			target_handle = other.handle
		else:
			target_handle = other			
		try:
			return self.handle.remove_link(target_handle)
		except Exception:
			return False

	def set_dsp(self, proc, user=0, priority=0):
		"""Sets up a user DSP function on the sound channel."""
		if self.handle:
			return self.handle.set_dsp(proc, user, priority)

	def remove_dsp(self, dsp_handle):
		"""Removes a DSP function from the sound channel."""
		if self.handle:
			return self.handle.remove_dsp(dsp_handle)

	@property
	def position(self):
		if not self.handle:
			return 0
		try:
			channel = self.dedata if getattr(self, "_hrtf_stream", False) else self.handle
			return int(channel.bytes_to_seconds(channel.get_position()) * 1000)
		except Exception as e:
			print(e)
			return 0

	@position.setter
	def position(self, ms_value):
		if not self.handle:
			return
		try:
			seconds = float(ms_value) / 1000.0
			channel = self.dedata if getattr(self, "_hrtf_stream", False) else self.handle
			byte_target = channel.seconds_to_bytes(seconds)
			channel.set_position(byte_target)
			if getattr(self, "_hrtf_stream", False) or getattr(self, "_hrtf_dsp", 0):
				_hrtf.BASS_HRTF_Reset(self._get_raw_channel_handle())
		except Exception as e:
			print(e)

	def seek(self, ms_value):
		self.position = ms_value

	# =========================================================================
	# HỆ THỐNG TRỘN 3D ĐA NĂNG (HỖ TRỢ HRTF + PAN/VOL/PITCH TÙY CHỈNH CỦA USER)
	# =========================================================================

	def _compute_rotated_delta(self, listener_x, listener_y, listener_z, source_x, source_y, source_z, rotation=0.0):
		dx = float(source_x - listener_x)
		dy = float(source_y - listener_y)
		dz = float(source_z - listener_z)
		if abs(rotation) > 0.001:
			rad = math.radians(rotation)
			cos_a = math.cos(rad)
			sin_a = math.sin(rad)
			rx = cos_a * dx - sin_a * dy
			ry = sin_a * dx + cos_a * dy
			dx, dy = rx, ry
		return dx, dy, dz

	def set3d(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	          rotation=0, head=180, pan_step=2.5, volume_step=2.5,
	          behind_pitch_decrease=0, behind_volume_decrease=0,
	          pitch_step=1, pitch_range=92, pan_range=70,
	          start_pan=0, start_volume=100, start_pitch=100,
	          soft=False, mix_pan_with_hrtf=False, bilinear=True):
		"""Định vị âm thanh 3D thông minh:
		- Hệ trục User: X = Ngang (Trái - / Phải +), Y = Dọc (Lùi - / Tiến +), Z = Cao (Thấp - / Cao +).
		- Nếu soft=True hoặc kênh đã gắn HRTF (Stream/DSP): Dùng Steam Audio HRTF nguyên thủy,
		  NHƯNG vẫn tôn trọng `start_pan`, `start_volume`, `start_pitch`, `behind_pitch_decrease`,
		  và `user_pan_offset` / `user_volume_offset` để user tự do tinh chỉnh thêm!
		- Nếu mix_pan_with_hrtf=True: Trộn thêm cả độ lệch Pan của math3d chồng lên HRTF.
		"""
		use_hrtf = bool(soft or getattr(self, "_hrtf_stream", False) or getattr(self, "_hrtf_dsp", 0))
		if use_hrtf:
			return self.set3dsoft(
				listener_x, listener_y, listener_z, source_x, source_y, source_z,
				rotation=rotation,
				start_pan=start_pan, start_volume=start_volume, start_pitch=start_pitch,
				pan_step=pan_step if mix_pan_with_hrtf else 0.0,
				volume_step=volume_step,
				behind_pitch_decrease=behind_pitch_decrease,
				behind_volume_decrease=behind_volume_decrease,
				pitch_step=pitch_step, pitch_range=pitch_range, pan_range=pan_range,
				bilinear=bilinear
			)
		return self.math3d(
			listener_x, listener_y, listener_z, source_x, source_y, source_z,
			pan_step, volume_step, behind_pitch_decrease, behind_volume_decrease,
			pitch_step, pitch_range, pan_range, start_pan, start_volume, start_pitch,
			soft=False, rotation=rotation
		)

	def set3dsoft(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	              rotation=0, start_volume=100, volume_step=2.5, start_pitch=100,
	              start_pan=0, pan_step=0.0, behind_pitch_decrease=0, behind_volume_decrease=0,
	              pitch_step=0, pitch_range=92, pan_range=70, bilinear=True):
		"""Cập nhật HRTF 3D (hỗ trợ cả DSP Mode lẫn Stream Mode) và trộn mượt với thông số Pan/Volume/Pitch của User."""
		if not self._hrtf_stream and not self._hrtf_dsp:
			# Ưu tiên gắn DSP siêu nhẹ trước (dùng được cho cả Sample, MIDI, Mixer, Stream Stereo)
			if not self.attach_hrtf_dsp():
				# Nếu là kênh Mono Decode truyền thống thì dùng StreamCreate
				if hasattr(self, "_attach_hrtf"):
					self._attach_hrtf()
				else:
					return False

		raw = self._get_raw_channel_handle()
		if not raw:
			return False
		hrtf = _initialize_hrtf()

		# Tính tọa độ tương đối đã xoay theo góc nhìn người nghe (rotation)
		dx, dy, dz = self._compute_rotated_delta(listener_x, listener_y, listener_z, source_x, source_y, source_z, rotation)
		distance = math.sqrt(dx * dx + dy * dy + dz * dz)

		# Tính suy giảm khoảng cách mượt mà:
		# Kết hợp đường cong mượt để khi nhích 1 int tọa độ không bị xa quá mức
		if volume_step > 0:
			step_ratio = float(volume_step) / 100.0
			linear_atten = max(0.0, 1.0 - distance * step_ratio)
			smooth_atten = 1.0 / (1.0 + (step_ratio * 1.5) * max(0.0, distance - 0.5))
			attenuation = min(1.0, (linear_atten * 0.65) + (smooth_atten * 0.35))
			if linear_atten <= 0.0:
				attenuation = 0.0
		else:
			attenuation = -1.0  # Để C tự tính theo DistanceModel

		# Gửi trực tiếp tọa độ User (X=Ngang, Y=Dọc, Z=Cao) vào C v3.0
		# C v3.0 đã tự chuyển trục sang Steam Audio và giữ HRTF nguyên thủy (không lọc EQ)
		if not hrtf.BASS_HRTF_Set3D(raw, dx, dy, dz, float(attenuation), 1 if bilinear else 0):
			return False

		self._3d = (listener_x, listener_y, listener_z, source_x, source_y, source_z)

		# Tính toán trộn thêm Pan / Volume / Pitch của User (nếu user muốn tùy biến thêm)
		final_vol = float(start_volume) + float(self.user_volume_offset)
		final_pan = float(start_pan) + float(self.user_pan_offset)
		final_pitch = float(start_pitch) + float(self.user_pitch_offset)

		if pan_step != 0.0:
			final_pan += dx * float(pan_step)
			final_pan = max(min(final_pan, float(pan_range)), -float(pan_range))

		if behind_pitch_decrease != 0 or behind_volume_decrease != 0 or pitch_step != 0:
			is_behind = dy < 0
			is_below = dz < 0
			is_front = dy > 0
			is_rising = dz > 0
			if is_front and is_rising:
				final_pitch += (pitch_step + behind_pitch_decrease)
				final_vol += behind_volume_decrease
			elif is_behind or is_below:
				final_pitch -= (pitch_step + behind_pitch_decrease)
				final_vol -= behind_volume_decrease
			final_pitch = max(min(final_pitch, start_pitch + 5), pitch_range)

		self.pan = max(-100.0, min(100.0, final_pan))
		self.volume = max(0.0, min(100.0, final_vol))
		self.pitch = max(5.0, final_pitch)
		return True

	def math3d(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	           pan_step, volume_step, behind_pitch_decrease, behind_volume_decrease,
	           pitch_step, pitch_range, pan_range, start_pan, start_volume, start_pitch,
	           soft=False, rotation=0.0):
		if soft or getattr(self, "_hrtf_stream", False) or getattr(self, "_hrtf_dsp", 0):
			return self.set3dsoft(
				listener_x, listener_y, listener_z, source_x, source_y, source_z,
				rotation=rotation, start_volume=start_volume, volume_step=volume_step,
				start_pitch=start_pitch, start_pan=start_pan,
				behind_pitch_decrease=behind_pitch_decrease,
				behind_volume_decrease=behind_volume_decrease,
				pitch_step=pitch_step, pitch_range=pitch_range, pan_range=pan_range
			)

		dx, dy, dz = self._compute_rotated_delta(listener_x, listener_y, listener_z, source_x, source_y, source_z, rotation)
		final_pan = start_pan + self.user_pan_offset + dx * pan_step

		delta_y = abs(dy)
		delta_z = abs(dz)
		# Khoảng cách Euclidean mượt kết hợp hệ số chiều cao
		horiz_dist = math.sqrt(dx * dx + dy * dy)
		final_volume = (start_volume + self.user_volume_offset) - (horiz_dist + delta_z * 0.5) * volume_step
		final_volume = max(min(final_volume, 100.0), 0.0)
		final_pitch = start_pitch + self.user_pitch_offset

		is_behind = dy < 0
		is_below = dz < 0
		is_front = dy > 0
		is_rising = dz > 0

		if is_front and is_rising:
			final_pitch += (pitch_step + behind_pitch_decrease)
			final_volume += behind_volume_decrease
		elif is_behind or is_below:
			final_pitch -= (pitch_step + behind_pitch_decrease)
			final_volume -= behind_volume_decrease

		final_pitch = max(min(final_pitch, start_pitch + 1), pitch_range)
		final_pan = max(min(final_pan, pan_range), -pan_range)

		self.volume = final_volume
		self.pitch = final_pitch
		self.pan = final_pan
		return True

	def slide3d(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	            fatime, rotation=0, head=180, pan_step=2.5, volume_step=2.5,
	            behind_pitch_decrease=0, behind_volume_decrease=0, pitch_step=1,
	            pitch_range=92, pan_range=75, start_pan=0, start_volume=100, start_pitch=100):
		if getattr(self, "_hrtf_stream", False) or getattr(self, "_hrtf_dsp", 0):
			return self.set3dsoft(
				listener_x, listener_y, listener_z, source_x, source_y, source_z,
				rotation=rotation, start_volume=start_volume, volume_step=volume_step,
				start_pitch=start_pitch, start_pan=start_pan
			)
		self.math3dslide(
			listener_x, listener_y, listener_z, source_x, source_y, source_z,
			pan_step, volume_step, behind_pitch_decrease, behind_volume_decrease,
			pitch_step, pitch_range, pan_range, start_pan, start_volume, start_pitch,
			fatime=fatime, rotation=rotation
		)

	def math3dslide(self, listener_x, listener_y, listener_z, source_x, source_y, source_z,
	                pan_step, volume_step, behind_pitch_decrease, behind_volume_decrease,
	                pitch_step, pitch_range, pan_range, start_pan, start_volume, start_pitch,
	                fatime, rotation=0.0):
		dx, dy, dz = self._compute_rotated_delta(listener_x, listener_y, listener_z, source_x, source_y, source_z, rotation)
		final_pan = start_pan + self.user_pan_offset + dx * pan_step
		horiz_dist = math.sqrt(dx * dx + dy * dy)
		delta_z = abs(dz)
		final_volume = (start_volume + self.user_volume_offset) - (horiz_dist + delta_z * 0.5) * volume_step
		final_volume = max(min(final_volume, 100.0), 0.0)
		final_pitch = start_pitch + self.user_pitch_offset

		is_behind = dy < 0
		is_below = dz < 0
		is_front = dy > 0
		is_rising = dz > 0

		if is_front and is_rising:
			final_pitch += (pitch_step + behind_pitch_decrease)
			final_volume += behind_volume_decrease
		elif is_behind or is_below:
			final_pitch -= (pitch_step + behind_pitch_decrease)
			final_volume -= behind_volume_decrease

		final_pitch = max(min(final_pitch, start_pitch + 1), pitch_range)
		final_pan = max(min(final_pan, pan_range), -pan_range)
		self.handle.slide_attribute("volume", float(final_volume) / 100.0, fatime)
		self.handle.slide_attribute("pan", float(final_pan) / 100.0, fatime)
		self.handle.slide_attribute("frequency", (float(final_pitch) / 100.0) * self.freq, fatime)


class vst(SoundBase):
	"""
	VST Class inheriting from SoundBase. 
	Handles Virtual Studio Technology (VSTi instruments and VST DSP effects).
	"""
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.handle = None
		self.vst_handle = None
		self._target_channel = None
		self.freq = 44100
		self.chans = 2
		self.paused = False

	def create_instrument(self, dll_path, frequency=44100, channels=2, flags=0, ThreeD=False):
		"""
		Initializes a new VSTi (Virtual Instrument) audio stream.
		"""
		self.close()
		self.freq = frequency
		self.chans = channels

		encoded_path = dll_path.encode('utf-8') if isinstance(dll_path, str) else dll_path
		raw_vst_handle = pybassvst.BASS_VST_ChannelCreate(frequency, channels, encoded_path, flags | (0x100 if ThreeD else 0))
		
		if not raw_vst_handle:
			return False
		self.handle = sound_lib.channel.Channel(raw_vst_handle)
		self.vst_handle = raw_vst_handle
		if ThreeD:
			self.attach_hrtf_dsp()
		return True

	def set_dsp(self, target_stream, dll_path, priority=0):
		"""
		Assigns a VST plugin as a DSP effect to an active audio stream.
		"""
		if not target_stream or not hasattr(target_stream, "handle"):
			return False

		raw_channel = target_stream.handle.handle if hasattr(target_stream.handle, "handle") else target_stream.handle
		if hasattr(raw_channel, "value"):
			raw_channel = raw_channel.value

		encoded_path = dll_path.encode('utf-8') if isinstance(dll_path, str) else dll_path
		self.vst_handle = pybassvst.BASS_VST_ChannelSetDSP(raw_channel, encoded_path, 0, priority)
		
		if self.vst_handle:
			self.handle = target_stream.handle
			self._target_channel = raw_channel 
			return True
		return False

	def remove_dsp(self):
		"""
		Safely detaches and removes the VST DSP effect from the host channel.
		"""
		if not self.vst_handle or not self._target_channel:
			return False
			
		success = pybassvst.BASS_VST_ChannelRemoveDSP(self._target_channel, self.vst_handle)
		if success:
			self.vst_handle = None
			self._target_channel = None
			self.handle = None
		return bool(success)

	def get_info(self):
		if not self.vst_handle:
			return None
		info = pybassvst.BASS_VST_INFO()
		if pybassvst.BASS_VST_GetInfo(self.vst_handle, ctypes.byref(info)):
			return info
		return None

	def send_midi(self, midi_channel, midi_event, midi_velocity):
		if not self.vst_handle:
			return False
		return bool(pybassvst.BASS_VST_ProcessEvent(self.vst_handle, midi_channel, midi_event, midi_velocity))

	def set_param(self, index, value):
		if not self.vst_handle:
			return False
		return bool(pybassvst.BASS_VST_SetParam(self.vst_handle, int(index), float(value)))

	def get_param(self, index):
		if not self.vst_handle:
			return 0.0
		return pybassvst.BASS_VST_GetParam(self.vst_handle, int(index))

	def set_program(self, index):
		if not self.vst_handle:
			return False
		return bool(pybassvst.BASS_VST_SetProgram(self.vst_handle, int(index)))

	def set_bypass(self, state):
		if not self.vst_handle:
			return False
		return bool(pybassvst.BASS_VST_SetBypass(self.vst_handle, ctypes.c_byte(1 if state else 0)))

	def get_chunk(self, is_preset=True):
		if not self.vst_handle:
			return None
		chunk_ptr = ctypes.c_void_p()
		length = pybassvst.BASS_VST_GetChunk(self.vst_handle, ctypes.c_byte(1 if is_preset else 0), ctypes.byref(chunk_ptr))
		if length > 0 and chunk_ptr:
			return ctypes.string_at(chunk_ptr, length)
		return None

	def set_chunk(self, chunk_bytes, is_preset=True):
		if not self.vst_handle or not chunk_bytes:
			return False
		return bool(pybassvst.BASS_VST_SetChunk(self.vst_handle, ctypes.c_byte(1 if is_preset else 0), chunk_bytes, len(chunk_bytes)))

	def play(self):
		if self.handle:
			self.handle.play()

	def stop(self):
		if self.handle and self.handle.is_playing:
			self.handle.stop()
			self.handle.set_position(0)

	def close(self):
		try:
			self.detach_hrtf_dsp()
			if self.handle and self.playing:
				self.handle.stop()
			if self.vst_handle:
				pybassvst.BASS_VST_ChannelFree(self.vst_handle)
				self.vst_handle = None
			if self.handle:
				self.handle.free()
				self.handle = None
			if self.sound_token in buffer.hSound_poolbuffers:
				del buffer.hSound_poolbuffers[self.sound_token]
		except Exception:
			pass


class mixer(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.handle = None
		self.freq = 44100
		self.chans = 2
		self.paused = False
		self.boolfadein = False
		self.sources = {}

	def _get_raw_handle(self, obj):
		if obj is None:
			return 0
		if hasattr(obj, "dedata") and obj.dedata:
			obj = obj.dedata
		if hasattr(obj, "handle") and obj.handle:
			obj = obj.handle
		if hasattr(obj, "handle"):
			obj = obj.handle
		if hasattr(obj, "value"):
			return ctypes.c_ulong(obj.value).value
		return ctypes.c_ulong(int(obj)).value

	def create(
		self,
		frequency=44100,
		channels=2,
		flags=bassmix.BASS_MIXER_NONSTOP | bassmix.BASS_MIXER_RESUME,
		ThreeD=False,
	):
		"""Initializes a new Mixer Stream (supports ThreeD=True via AttachDSP)."""
		self.close()
		self.freq = frequency
		self.chans = channels

		raw_handle = bassmix.BASS_Mixer_StreamCreate(frequency, channels, flags | (0x100 if ThreeD else 0))
		if not raw_handle:
			return False

		if hasattr(sound_lib, "channel") and hasattr(sound_lib.channel, "Channel"):
			self.handle = sound_lib.channel.Channel(raw_handle)
		else:
			from .sound_lib.stream import Stream as BaseStream
			self.handle = BaseStream(handle=raw_handle)

		if ThreeD:
			self.attach_hrtf_dsp()
		return True

	def add(self, source, flags=0, start=None, length=None):
		if not self.handle:
			return False
		raw_source = self._get_raw_handle(source)
		if not raw_source:
			return False
		mixer_handle = self._get_raw_handle(self.handle)

		if start is not None and length is not None:
			res = bassmix.BASS_Mixer_StreamAddChannelEx(mixer_handle, raw_source, flags, start, length)
		else:
			res = bassmix.BASS_Mixer_StreamAddChannel(mixer_handle, raw_source, flags)

		if bool(res):
			self.sources[raw_source] = source
			return True
		return False

	def remove(self, source):
		raw_source = self._get_raw_handle(source)
		if raw_source in self.sources:
			del self.sources[raw_source]
		return bool(bassmix.BASS_Mixer_ChannelRemove(raw_source))

	def pause_channel(self, source, paused=True):
		raw_source = self._get_raw_handle(source)
		flag = bassmix.BASS_MIXER_PAUSE if paused else 0
		return bassmix.BASS_Mixer_ChannelFlags(raw_source, flag, bassmix.BASS_MIXER_PAUSE) != -1

	def set_channel_pos(self, source, ms_value):
		raw_source = self._get_raw_handle(source)
		if not raw_source:
			return False
		sec = float(ms_value) / 1000.0
		byte_target = sound_lib.main.BASS_ChannelSeconds2Bytes(raw_source, sec)
		return bool(bassmix.BASS_Mixer_ChannelSetPosition(raw_source, byte_target, 0))

	def get_channel_pos(self, source):
		raw_source = self._get_raw_handle(source)
		byte_pos = bassmix.BASS_Mixer_ChannelGetPosition(raw_source, 0)
		if byte_pos == -1:
			return 0
		sec = sound_lib.main.BASS_ChannelBytes2Seconds(raw_source, byte_pos)
		return int(sec * 1000)

	def get_channel_level(self, source):
		raw_source = self._get_raw_handle(source)
		return bassmix.BASS_Mixer_ChannelGetLevel(raw_source)

	def set_matrix(self, source, matrix_data):
		raw_source = self._get_raw_handle(source)
		flat_list = []
		if isinstance(matrix_data[0], (list, tuple)):
			for row in matrix_data:
				flat_list.extend(row)
		else:
			flat_list = matrix_data

		arr = (ctypes.c_float * len(flat_list))(*flat_list)
		return bool(bassmix.BASS_Mixer_ChannelSetMatrix(raw_source, ctypes.cast(arr, ctypes.POINTER(ctypes.c_float))))

	def set_envelope(self, source, env_type, nodes):
		raw_source = self._get_raw_handle(source)
		c_nodes = []
		for node in nodes:
			if isinstance(node, (tuple, list)):
				c_node = bassmix.BASS_MIXER_NODE()
				c_node.pos = node[0]
				c_node.value = float(node[1])
				c_nodes.append(c_node)
			else:
				c_nodes.append(node)

		arr = (bassmix.BASS_MIXER_NODE * len(c_nodes))(*c_nodes)
		return bool(
			bassmix.BASS_Mixer_ChannelSetEnvelope(
				raw_source,
				env_type,
				ctypes.cast(arr, ctypes.POINTER(bassmix.BASS_MIXER_NODE)),
				len(c_nodes),
			)
		)

	def play(self):
		if self.handle:
			self.handle.play()

	def stop(self):
		if self.handle and self.handle.is_playing:
			self.handle.stop()
			self.handle.set_position(0)

	def close(self):
		try:
			self.detach_hrtf_dsp()
			if self.handle and self.playing:
				self.handle.stop()
			for raw_src in list(self.sources.keys()):
				bassmix.BASS_Mixer_ChannelRemove(raw_src)
			self.sources.clear()

			if self.handle:
				self.handle.free()
				self.handle = None
			if self.sound_token in buffer.hSound_poolbuffers:
				del buffer.hSound_poolbuffers[self.sound_token]
		except Exception:
			pass


class record(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		self.encoder_token = utils.token(max=25)
		buffer.hrecordthreadbuffers[self.sound_token] = self
		self.handle = None
		self.encoder = None
		self._paused = False
		self._sample_data = bytearray()
		self._mode = "w"
		self._internal_proc = None

	def stream(self, filename="", frequency=44100, channels=2, mode="w", callback=None):
		self.close()
		self._mode = mode
		self._sample_data = bytearray()
		record_proc = None

		if mode in ("c", "s"):
			def _internal_callback(handle, buffer_ptr, length, user):
				if length > 0:
					data = ctypes.string_at(buffer_ptr, length)
					if self._mode == "s":
						self._sample_data.extend(data)
					elif self._mode == "c" and callback:
						if callback(data) is False:
							return False
				return True
			self._internal_proc = _internal_callback
			record_proc = self._internal_proc

		if record_proc:
			self.handle = Recording(frequency=frequency, channels=channels, proc=record_proc)
		else:
			self.handle = Recording(frequency=frequency, channels=channels)
		self.handle.play()

		if filename and mode == "w":
			self.encoder = self.drawn(self.handle, filename)
		self._paused = False

	def get_sample(self):
		return bytes(self._sample_data)

	def clear_sample(self):
		self._sample_data = bytearray()

	def drawn(self, h, filename):
		e = Encoder(h, system.match(system.embedded_data_path(), "..", filename))
		self.encoder_token = utils.token(max=36)
		buffer.hrecordthreadbuffers[self.encoder_token] = e
		return e

	def stop(self):
		if self.encoder:
			self.encoder.stop()
			self.encoder = None
		if self.handle:
			self.handle.stop()
			self.handle.free()
			self.handle = None

	def close(self):
		try:
			self.stop()
			if self.sound_token in buffer.hrecordthreadbuffers:
				del buffer.hrecordthreadbuffers[self.sound_token]
			if self.encoder_token in buffer.hrecordthreadbuffers:
				del buffer.hrecordthreadbuffers[self.encoder_token]
		except Exception:
			pass


class musical(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.handle = None
		self.freq = 44100
		self.paused = False
		self.boolfadein = False
		self.fonts_storage = []

	def load_font(self, font_path, flags=0):
		font_path = system.match(system.embedded_data_path(), "..", font_path)
		sf = SoundFont(font_path, flags=flags)
		self.fonts_storage.append(sf) 
		return sf

	def create_empty_stream(self, channels=16, ThreeD=False):
		if self.handle:
			self.close()
		self.handle = MIDIStream(channels=channels, decode=False)
		self.freq = int(self.handle.get_frequency())
		if ThreeD:
			self.attach_hrtf_dsp()

	def stream(self, filename, mono=False, ThreeD=False):
		if self.handle:
			self.close()
		# Nếu bật ThreeD cho MIDI, giữ Stereo (mono=False) để gắn DSP HRTF trực tiếp
		self.handle = MIDIFileStream(file=filename, mono=False if ThreeD else mono, decode=False)
		self.freq = int(self.handle.get_frequency())
		if ThreeD:
			self.attach_hrtf_dsp()
		if self.handle: 
			return int(self.handle.bytes_to_seconds(self.handle.get_length()) * 1000)

	def set_fonts(self, fonts_config):
		if not self.handle or not hasattr(self.handle, 'set_fonts'):
			return False
		if isinstance(fonts_config, SoundFont):
			return self.handle.set_fonts([(fonts_config.handle, -1, 0)])
		return self.handle.set_fonts(fonts_config)

	def send_event(self, chan, event, param):
		if self.handle and hasattr(self.handle, 'send_event'):
			return self.handle.send_event(chan, event, param)
		return False

	def load_samples(self):
		if self.handle and hasattr(self.handle, 'load_samples'):
			return self.handle.load_samples(0, 0)
		return False

	def play_wait(self):
		self.handle.looping = False
		if self.boolfadein: 
			self.handle.set_volume(0)
		self.handle.play_blocking()

	def play_looped(self):
		if self.boolfadein: 
			self.handle.set_volume(0)
		self.handle.looping = True
		self.handle.play()

	def stop(self):
		if self.handle and self.handle.is_playing:
			self.handle.stop()
			self.handle.set_position(0)

	def play(self):
		if self.handle:
			self.handle.play()

	def close(self):
		try:
			self.detach_hrtf_dsp()
			if self.handle and self.playing:
				self.handle.stop()
			if self.handle: 
				self.handle.free()
				self.handle = None

			for sf in self.fonts_storage:
				sf.free()
			self.fonts_storage = []

			if self.sound_token in buffer.hmidibuffers:
				del buffer.hmidibuffers[self.sound_token]
		except Exception: 
			pass


class sound(SoundBase):
	def __init__(self):
		super().__init__()
		self.sound_token = utils.token(max=25)
		buffer.hSound_poolbuffers[self.sound_token] = self
		self.handle = None
		self.dedata = None
		self._3d = None
		self._hrtf_stream = False
		self.freq = 44100
		self.paused = False
		self.boolfadein = False

	def stream(self, filename, draw=False, mono=False, ThreeD=False, decode=False, autofree=False, use_dsp_hrtf=False):
		"""Nạp một Stream âm thanh.
		- Nếu ThreeD=True và use_dsp_hrtf=True: Giữ Stereo, gắn DSP HRTF trực tiếp (siêu nhẹ, dùng chung được với Tempo!).
		- Nếu ThreeD=True và use_dsp_hrtf=False (mặc định): Tạo stream HRTF từ kênh Mono Decode (hỗ trợ cả file Mono gốc).
		"""
		if self.handle:
			self.close()
			
		self.filename = filename
		self.draw = draw
		self.autofree = autofree
		self.is_tempo = False

		if ThreeD:
			_initialize_hrtf()
			if not use_dsp_hrtf:
				mono = True
		self.mono = mono
		source_flags = 0x100 if ThreeD else 0  # BASS_SAMPLE_FLOAT
		source_decode = decode or (ThreeD and not use_dsp_hrtf)
		source_autofree = autofree and not (ThreeD and not use_dsp_hrtf)
		if draw:
			handle = sound_lib.stream.PushStream(chans=1 if mono else 2, flags=source_flags, decode=source_decode, autofree=source_autofree)
		else:
			if filename in buffer.hstreambuffers:
				handle = sound_lib.stream.FileStream(mem=True, file=buffer.hstreambuffers[filename]["buffer"], length=buffer.hstreambuffers[filename]["len"], mono=mono, flags=source_flags, decode=source_decode, autofree=source_autofree)
			else:
				if not utils.is_url(filename):
					handle = sound_lib.stream.FileStream(file=filename, mono=mono, flags=source_flags, decode=source_decode, autofree=source_autofree)
				else: 
					handle = sound_lib.stream.URLStream(url=filename, mono=mono, flags=source_flags, decode=source_decode, autofree=source_autofree)
					
		self.handle = handle
		if ThreeD:
			try:
				if use_dsp_hrtf and not self. attach_hrtf_dsp():
					# Nếu file gốc là 1 kênh Mono nên AttachDSP từ chối -> Tự động chuyển sang StreamCreate
					self.handle.free()
					self.mono = True
					return self.stream(filename, draw=draw, mono=True, ThreeD=True, decode=decode, autofree=autofree, use_dsp_hrtf=False)
				elif not use_dsp_hrtf:
					self._attach_hrtf()
			except Exception:
				handle.free()
				self.handle = None
				raise
			
		self.freq = int(self.handle.get_frequency())
		buffer.hSound_poolbuffers[self.sound_token] = self
		try:
			target_h = self.dedata if self.dedata else self.handle
			if target_h:
				return int(target_h.bytes_to_seconds(target_h.get_length()) * 1000)
		except Exception:
			return 0

	def load(self, filename="", mono=False, ThreeD=False):
		if self.handle:
			self.close()
		if not isinstance(filename, str):
			self.keep = self.handle = sound_lib.sample.SampleBasedChannel(filename)
			self.freq = self.handle.get_frequency()
			if ThreeD:
				self.attach_hrtf_dsp()
			return
		if filename in buffer.hsamplebuffers:
			self.handle = sound_lib.sample.SampleBasedChannel(buffer.hsamplebuffers[filename]["buffer"])
		else:
			self.handle = sound_lib.sample.SampleBasedChannel(sound_lib.sample.Sample(filename, mono=mono))
		self.freq = self.handle.get_frequency()
		if ThreeD:
			self.attach_hrtf_dsp()

	def vsample(self, sample=None, ThreeD=False):
		if self.handle:
			self.close()
		self.handle = sound_lib.sample.SampleBasedChannel(sample)
		self.freq = self.handle.get_frequency()
		if ThreeD:
			self.attach_hrtf_dsp()

	def sample(self, filename):
		return sound_lib.sample.Sample(filename)

	def _attach_hrtf(self):
		if self._hrtf_stream or self._hrtf_dsp:
			return
		hrtf = _initialize_hrtf()
		source = self.handle
		if not source:
			raise RuntimeError("Load a ThreeD stream before setting its HRTF position")
		raw = self._get_raw_channel_handle()
		# Thử tạo HRTF Stream cho nguồn Mono Decode
		rendered = hrtf.BASS_HRTF_StreamCreate(raw, 0)
		if rendered:
			self.dedata = source
			self.handle = sound_lib.stream.BaseStream(rendered)
			self._hrtf_stream = True
			return
		# Nếu nguồn là kênh Stereo đang phát (không phải Mono Decode), tự động gắn DSP!
		if self.attach_hrtf_dsp():
			return
		raise RuntimeError("BASS_HRTF failed; use stream(..., ThreeD=True) or a Stereo channel for AttachDSP")

	def play_wait(self):
		if self._hrtf_stream and self.dedata:
			self.dedata.looping = False
		self.handle.looping = False
		if self.boolfadein:
			self.handle.set_volume(0)
		self.handle.play_blocking()

	def play_looped(self):
		if self.boolfadein:
			self.handle.set_volume(0)
		if self.play3d(loop=True):
			return
		self.handle.looping = True
		self.handle.play()

	def stop(self):
		if self.handle:
			self.handle.stop()
		if self._hrtf_stream:
			self.position = 0
		elif self.handle:
			self.handle.set_position(0)
			if self.dedata:
				self.dedata.set_position(0)

	def close(self):
		try:
			self.detach_hrtf_dsp()
			if self.handle:
				self.handle.stop()
				self.handle.free()
		finally:
			self.handle = None
			try:
				if self.dedata:
					self.dedata.free()
			finally:
				self.dedata = None
				self._hrtf_stream = False
				self._hrtf_dsp = 0
				self._3d = None
				self.active_fx_handles.clear()
				buffer.hSound_poolbuffers.pop(self.sound_token, None)

	def play3d(self, loop=False):
		if not self._hrtf_stream:
			return False
		self.dedata.looping = loop
		self.handle.play()
		return True

	def play(self):
		if self.play3d():
			return
		self.handle.play()

	def _ensure_tempo(self):
		if getattr(self, "is_tempo", False):
			return True

		if self._hrtf_stream:
			raise RuntimeError("Tempo conversion requires stream(..., ThreeD=True, use_dsp_hrtf=True)")

		was_playing = self.playing
		had_hrtf_dsp = bool(self._hrtf_dsp)
		if had_hrtf_dsp:
			self.detach_hrtf_dsp()

		current_pos = self.position
		current_vol = self.volume
		current_pitch = getattr(self, 'pitch', 100)
		current_pan = self.pan
		active_fxs = list(self.active_fx_handles.keys())

		if self.draw:
			new_dedata = sound_lib.stream.PushStream(decode=True)
			new_dedata.push(b'\x00' * 8192)
		else:
			if self.filename in buffer.hstreambuffers:
				new_dedata = sound_lib.stream.FileStream(mem=True, file=buffer.hstreambuffers[self.filename]["buffer"], length=buffer.hstreambuffers[self.filename]["len"], mono=self.mono, decode=True, autofree=self.autofree)
			else:
				if not utils.is_url(self.filename):
					new_dedata = sound_lib.stream.FileStream(file=self.filename, mono=self.mono, decode=True, autofree=self.autofree)
				else: 
					new_dedata = sound_lib.stream.URLStream(url=self.filename, mono=self.mono, decode=True, autofree=self.autofree)

		raw_source = new_dedata.handle if hasattr(new_dedata, 'handle') else new_dedata
		if hasattr(raw_source, 'value'):
			raw_source = raw_source.value

		tempo_handle = pybass_fx.BASS_FX_TempoCreate(raw_source, 0x10000)
		if not tempo_handle:
			new_dedata.free()
			if had_hrtf_dsp:
				self.attach_hrtf_dsp()
			return False
			
		if self.handle:
			self.handle.stop()
			self.handle.free()
		if self.dedata:
			self.dedata.free()
			
		self.dedata = new_dedata
		self.handle = sound_lib.channel.Channel(tempo_handle)
		self.is_tempo = True

		if had_hrtf_dsp:
			self.attach_hrtf_dsp()
		if was_playing:
			self.handle.play()
		self.position = current_pos
		self.volume = current_vol
		self.pitch = current_pitch
		self.pan = current_pan
		for fx_key in active_fxs:
			self.setfx(fx_key)
		return True

	def get_tempo(self):
		if not getattr(self, "is_tempo", False) or not self.handle:
			return 0.0
		return self.handle.get_attribute(65536)

	def set_tempo(self, value):
		if float(value) == 0.0 and not getattr(self, "is_tempo", False):
			return
		if self._ensure_tempo():
			self.handle.set_attribute(65536, float(value))

	def get_tone(self):
		if not getattr(self, "is_tempo", False) or not self.handle:
			return 0.0
		return self.handle.get_attribute(65537)

	def set_tone(self, value, fft_size=2048, osamp=8):
		if float(value) == 0.0 and not getattr(self, "is_tempo", False):
			return
		if self._ensure_tempo():
			self.handle.set_attribute(65537, float(value))

	def get_tempo_freq(self):
		if not getattr(self, "is_tempo", False) or not self.handle:
			return 0.0
		return self.handle.get_attribute(65538)

	def set_tempo_freq(self, value):
		if float(value) == 0.0 and not getattr(self, "is_tempo", False):
			return
		if self._ensure_tempo():
			self.handle.set_attribute(65538, float(value))

	def push(self, data):
		try:
			if (getattr(self, "is_tempo", False) or self._hrtf_stream) and self.dedata:
				self.dedata.push(data)
				if self.handle and not getattr(self, "paused", False):
					if self.handle.is_stalled or self.handle.is_stopped:
						self.handle.play()
			else:
				if self.handle is None or not self.handle:
					return
				self.handle.push(data)
				if not getattr(self, "paused", False):
					if self.handle.is_stalled or self.handle.is_stopped:
						self.handle.play()
		except Exception:
			pass


def playsingle(filename, volume=100, pitch=100, pan=0, mono=False, ThreeD=False):
	# play sound more easily
	if not filename:
		return
	s = sound()
	s.load(filename, mono=mono, ThreeD=ThreeD)
	s.volume = volume
	s.pitch = pitch
	s.pan = pan
	s.play()
	return s