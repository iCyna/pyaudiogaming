from .sound_lib.external.pybass import *
from .sound_lib.external.pybass_fx import *

class Bgfx:
	def __init__(self):
		self.fxs = {"large room": {"name": BASS_FX_DX8_REVERB, "param": self.large_room},
			"room": {"name": BASS_FX_DX8_REVERB, "param": self.room},
			"small room": {"name": BASS_FX_DX8_REVERB, "param": self.small_room},
			"room stone": {"name": BASS_FX_DX8_REVERB, "param": self.room_stone},
			"long hallway": {"name": BASS_FX_DX8_REVERB, "param": self.long_hallway},
			"forest": {"name": BASS_FX_DX8_CHORUS, "param": self.forest},
			"city": {"name": BASS_FX_DX8_REVERB, "param": self.city}
		}

	def large_room(self):
		reverb_params = BASS_DX8_REVERB()
		reverb_params.fInGain = 0.0           # Giữ nguyên âm lượng gốc
		reverb_params.fReverbMix = -21.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		reverb_params.fReverbTime = 2000.0    # Thời gian vang dài (mô phỏng không gian lớn)
		reverb_params.fHighFreqRTRatio = 0.9  # Giảm tần số cao để âm trầm hơn
		return reverb_params

	def room(self):
		reverb_params = BASS_DX8_REVERB()
		reverb_params.fInGain = 0.0           # Giữ nguyên âm lượng gốc
		reverb_params.fReverbMix = -18.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		reverb_params.fReverbTime = 1000.0    # Thời gian vang dài (mô phỏng không gian lớn)
		reverb_params.fHighFreqRTRatio = 0.9  # Giảm tần số cao để âm trầm hơn
		return reverb_params

	def small_room(self):
		reverb_params = BASS_DX8_REVERB()
		reverb_params.fInGain = 0.0           # Giữ nguyên âm lượng gốc
		reverb_params.fReverbMix = -16.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		reverb_params.fReverbTime = 500.0    # Thời gian vang dài (mô phỏng không gian lớn)
		reverb_params.fHighFreqRTRatio = 0.6  # Giảm tần số cao để âm trầm hơn
		return reverb_params

	def city(self):
		reverb_params = BASS_DX8_REVERB()
		reverb_params.fInGain = 0.0           # Giữ nguyên âm lượng gốc
		reverb_params.fReverbMix = -80.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		reverb_params.fReverbTime = 3000.0    # Thời gian vang dài (mô phỏng không gian lớn)
		reverb_params.fHighFreqRTRatio = 0.6  # Giảm tần số cao để âm trầm hơn
		return reverb_params

	def room_stone(self):
		reverb_params = BASS_DX8_REVERB()
		reverb_params.fInGain = 0.0           # Giữ nguyên âm lượng gốc
		reverb_params.fReverbMix = -20.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		reverb_params.fReverbTime = 3000.0    # Thời gian vang dài (mô phỏng không gian lớn)
		reverb_params.fHighFreqRTRatio = 0.5  # Giảm tần số cao để âm trầm hơn
		return reverb_params

	def long_hallway(self):
		reverb_params = BASS_DX8_REVERB()
		reverb_params.fInGain = 0.0           # Giữ nguyên âm lượng gốc
		reverb_params.fReverbMix = -30.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		reverb_params.fReverbTime = 1800.0    # Thời gian vang dài (mô phỏng không gian lớn)
		reverb_params.fHighFreqRTRatio = 0.6  # Giảm tần số cao để âm trầm hơn
		return reverb_params

	def forest(self):
		chorus_params = BASS_DX8_CHORUS()
		chorus_params.fWetDryMix = 10.0            # Giữ nguyên âm lượng gốc
		chorus_params.fDepth =30.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		chorus_params.fFrequency=10.0    # Thời gian vang dài (mô phỏng không gian lớn)
		return chorus_params

	def city(self):
		reverb_params = BASS_DX8_REVERB()
		reverb_params.fInGain = 0.0           # Giữ nguyên âm lượng gốc
		reverb_params.fReverbMix = -80.0       # Mức trộn hiệu ứng reverb (giá trị thấp = ít vang)
		reverb_params.fReverbTime = 100.0    # Thời gian vang dài (mô phỏng không gian lớn)
		reverb_params.fHighFreqRTRatio = 0.6  # Giảm tần số cao để âm trầm hơn
		return reverb_params
