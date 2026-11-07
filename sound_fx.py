# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# BASS_FX environmental FX presets - Direct sound_modules & sound.cpp styleFX parser.

import math
from .sound_modules.pybass import *
from .sound_modules.pybass_fx import *

class Basic:
	"""Central BASS_FX preset collection & dynamic string FX parser."""
	def __init__(self):
		BASS_FX_GetVersion()
		self.fxs = {
			"large room": {"name": BASS_FX_DX8_REVERB, "param": self.large_room},
			"small room": {"name": BASS_FX_DX8_REVERB, "param": self.small_room},
			"hall": {"name": BASS_FX_DX8_REVERB, "param": self.hall},
			"long hallway": {"name": BASS_FX_DX8_REVERB, "param": self.long_hallway},
			"city": {"name": BASS_FX_DX8_REVERB, "param": self.city},
			"bedroom": {"name": BASS_FX_DX8_REVERB, "param": self.bedroom},
			"cave": {"name": BASS_FX_DX8_REVERB, "param": self.cave},
			"concert_arena": {"name": BASS_FX_DX8_REVERB, "param": self.concert_arena},
			"bathroom": {"name": BASS_FX_DX8_REVERB, "param": self.bathroom},
			"studio_vocal_booth": {"name": BASS_FX_DX8_REVERB, "param": self.studio_vocal_booth},
			"canyon": {"name": BASS_FX_DX8_REVERB, "param": self.canyon},
			"hallway_bright": {"name": BASS_FX_DX8_REVERB, "param": self.hallway_bright},
			"hallway_dark": {"name": BASS_FX_DX8_REVERB, "param": self.hallway_dark},
			"city_open": {"name": BASS_FX_DX8_REVERB, "param": self.city_open},
			"city_narrow": {"name": BASS_FX_DX8_REVERB, "param": self.city_narrow},
			"warehouse": {"name": BASS_FX_DX8_REVERB, "param": self.warehouse},
			"stone_room": {"name": BASS_FX_DX8_REVERB, "param": self.stone_room},
			"flanger_space": {"name": BASS_FX_BFX_FLANGER, "param": self.flanger_space},
			"flanger_tunnel": {"name": BASS_FX_BFX_FLANGER, "param": self.flanger_tunnel},
			"radio_distortion": {"name": BASS_FX_BFX_DISTORTION, "param": self.radio_distortion},
			"telephone_distortion": {"name": BASS_FX_BFX_DISTORTION, "param": self.telephone_distortion},
			"studio_compressor": {"name": BASS_FX_BFX_COMPRESSOR2, "param": self.studio_compressor},
			"voice_leveler": {"name": BASS_FX_BFX_COMPRESSOR2, "param": self.voice_leveler},
			"chorus_ensemble": {"name": BASS_FX_BFX_CHORUS, "param": self.chorus_ensemble},
			"chorus_wide": {"name": BASS_FX_BFX_CHORUS, "param": self.chorus_wide},
			"phaser_robot": {"name": BASS_FX_BFX_PHASER, "param": self.phaser_robot},
			"phaser_slow": {"name": BASS_FX_BFX_PHASER, "param": self.phaser_slow},
			"vinyl_lofi": {"name": BASS_FX_BFX_DISTORTION, "param": self.vinyl_lofi},
			"hard_limiter": {"name": BASS_FX_BFX_COMPRESSOR2, "param": self.hard_limiter},
		}
		self.filters = {
			"muffled_wall": {"name": BASS_FX_BFX_BQF, "param": self.bqf_lowpass_wall},
			"underwater": {"name": BASS_FX_BFX_LPF, "param": self.lpf_underwater},
			"telephone_line": {"name": BASS_FX_BFX_BQF, "param": self.bqf_bandpass_phone},
			"subwoofer_boost": {"name": BASS_FX_BFX_PEAKEQ, "param": self.peakeq_bass_boost},
			"eq_low_mid_scoop": {"name": BASS_FX_BFX_PEAKEQ, "param": self.eq_low_mid_scoop},
			"eq_presence_boost": {"name": BASS_FX_BFX_PEAKEQ, "param": self.eq_presence_boost},
			"eq_air_highs": {"name": BASS_FX_BFX_PEAKEQ, "param": self.eq_air_highs},
			"eq_mud_cut": {"name": BASS_FX_BFX_PEAKEQ, "param": self.eq_mud_cut},
			"bqf_highpass_radio": {"name": BASS_FX_BFX_BQF, "param": self.bqf_highpass_radio},
			"bqf_notch_60hz": {"name": BASS_FX_BFX_BQF, "param": self.bqf_notch_60hz},
			"bqf_peaking_mid": {"name": BASS_FX_BFX_BQF, "param": self.bqf_peaking_mid},
			"lpf_muffled_neighbor": {"name": BASS_FX_BFX_LPF, "param": self.lpf_muffled_neighbor},
			"megaphone_extreme": {"name": BASS_FX_BFX_BQF, "param": self.megaphone_extreme},
			"sub_bass_rumble": {"name": BASS_FX_BFX_BQF, "param": self.sub_bass_rumble},
			"hpf_crystal_clear": {"name": BASS_FX_BFX_BQF, "param": self.hpf_crystal_clear},
			"allpass_phase": {"name": BASS_FX_BFX_BQF, "param": self.allpass_phase},
			"low_shelf_warm": {"name": BASS_FX_BFX_BQF, "param": self.low_shelf_warm},
			"high_shelf_air": {"name": BASS_FX_BFX_BQF, "param": self.high_shelf_air},
			"low_shelf_dark": {"name": BASS_FX_BFX_BQF, "param": self.low_shelf_dark},
			"high_shelf_dark": {"name": BASS_FX_BFX_BQF, "param": self.high_shelf_dark},
			"lowpass_dark": {"name": BASS_FX_BFX_BQF, "param": self.lowpass_dark},
			"lowpass_voice_muffle": {"name": BASS_FX_BFX_BQF, "param": self.lowpass_voice_muffle},
			"lowpass_wall_soft": {"name": BASS_FX_BFX_BQF, "param": self.lowpass_wall_soft},
			"highpass_rumble_cut": {"name": BASS_FX_BFX_BQF, "param": self.highpass_rumble_cut},
			"highpass_light": {"name": BASS_FX_BFX_BQF, "param": self.highpass_light},
			"bandpass_walkie_talkie": {"name": BASS_FX_BFX_BQF, "param": self.bandpass_walkie_talkie},
			"bandpass_radio": {"name": BASS_FX_BFX_BQF, "param": self.bandpass_radio},
			"bandpass_voice": {"name": BASS_FX_BFX_BQF, "param": self.bandpass_voice},
			"presence_clarity": {"name": BASS_FX_BFX_BQF, "param": self.presence_clarity},
			"treble_sparkle": {"name": BASS_FX_BFX_BQF, "param": self.treble_sparkle},
			"mud_reduction": {"name": BASS_FX_BFX_BQF, "param": self.mud_reduction},
			"boxiness_cut": {"name": BASS_FX_BFX_BQF, "param": self.boxiness_cut},
		}

	# --- DX8 REVERB PRESETS ---
	def _dx8_reverb(self, in_gain=0.0, reverb_mix=-10.0, reverb_time=1000.0, hf_ratio=0.001):
		p = BASS_DX8_REVERB(); p.fInGain, p.fReverbMix, p.fReverbTime, p.fHighFreqRTRatio = float(in_gain), float(reverb_mix), float(reverb_time), float(hf_ratio); return p

	def small_room(self): return self._dx8_reverb(reverb_mix=-12.0, reverb_time=800.0)
	def large_room(self): return self._dx8_reverb(reverb_mix=-25.0, reverb_time=1500.0)
	def hall(self): return self._dx8_reverb(reverb_mix=-6.0, reverb_time=2200.0)
	def long_hallway(self): return self._dx8_reverb(reverb_mix=-10.0, reverb_time=1800.0)
	def hallway_bright(self): return self._dx8_reverb(reverb_mix=-8.0, reverb_time=1600.0, hf_ratio=0.5)
	def hallway_dark(self): return self._dx8_reverb(reverb_mix=-14.0, reverb_time=1500.0, hf_ratio=0.001)
	def city(self): return self._dx8_reverb(reverb_mix=-15.0, reverb_time=1200.0)
	def city_open(self): return self._dx8_reverb(reverb_mix=-31.0, reverb_time=120.0)
	def city_narrow(self): return self._dx8_reverb(reverb_mix=-10.0, reverb_time=1500.0)
	def bedroom(self): return self._dx8_reverb(reverb_mix=-18.0, reverb_time=500.0)
	def cave(self): return self._dx8_reverb(reverb_mix=-2.0, reverb_time=2800.0)
	def concert_arena(self): return self._dx8_reverb(reverb_mix=-4.0, reverb_time=2500.0)
	def bathroom(self): return self._dx8_reverb(reverb_mix=-10.0, reverb_time=900.0, hf_ratio=0.6)
	def studio_vocal_booth(self): return self._dx8_reverb(reverb_mix=-25.0, reverb_time=200.0)
	def canyon(self): return self._dx8_reverb(reverb_mix=0.0, reverb_time=3000.0)
	def warehouse(self): return self._dx8_reverb(reverb_mix=-6.0, reverb_time=2400.0)
	def stone_room(self): return self._dx8_reverb(reverb_mix=-9.0, reverb_time=1400.0, hf_ratio=0.8)

	# --- MODULATION / DISTORTION / DYNAMICS ---
	def flanger_space(self):
		p = BASS_BFX_FLANGER(); p.fWetDry, p.fSpeed, p.lChannel = 0.42, 0.028, BASS_BFX_CHANALL; return p
	def flanger_tunnel(self):
		p = BASS_BFX_FLANGER(); p.fWetDry, p.fSpeed, p.lChannel = 0.28, 0.012, BASS_BFX_CHANALL; return p
	def radio_distortion(self):
		p = BASS_BFX_DISTORTION(); p.fDrive, p.fDryMix, p.fWetMix, p.fFeedback, p.fVolume, p.lChannel = 2.2, 0.78, 0.58, 0.04, 1.0, BASS_BFX_CHANALL; return p
	def telephone_distortion(self):
		p = BASS_BFX_DISTORTION(); p.fDrive, p.fDryMix, p.fWetMix, p.fFeedback, p.fVolume, p.lChannel = 1.55, 0.86, 0.36, 0.02, 1.0, BASS_BFX_CHANALL; return p
	def vinyl_lofi(self):
		p = BASS_BFX_DISTORTION(); p.fDrive, p.fDryMix, p.fWetMix, p.fFeedback, p.fVolume, p.lChannel = 1.08, 0.90, 0.26, 0.0, 1.0, BASS_BFX_CHANALL; return p
	def studio_compressor(self):
		p = BASS_BFX_COMPRESSOR2(); p.fGain, p.fThreshold, p.fRatio, p.fAttack, p.fRelease, p.lChannel = 3.0, -20.0, 2.5, 10.0, 180.0, BASS_BFX_CHANALL; return p
	def voice_leveler(self):
		p = BASS_BFX_COMPRESSOR2(); p.fGain, p.fThreshold, p.fRatio, p.fAttack, p.fRelease, p.lChannel = 4.0, -24.0, 3.0, 14.0, 240.0, BASS_BFX_CHANALL; return p
	def hard_limiter(self):
		p = BASS_BFX_COMPRESSOR2(); p.fGain, p.fThreshold, p.fRatio, p.fAttack, p.fRelease, p.lChannel = 0.0, -2.0, 20.0, 1.0, 80.0, BASS_BFX_CHANALL; return p
	def chorus_ensemble(self):
		p = BASS_BFX_CHORUS(); p.fDryMix, p.fWetMix, p.fFeedback, p.fMinSweep, p.fMaxSweep, p.fRate, p.lChannel = 0.90, 0.42, 0.10, 0.8, 9.0, 1.3, BASS_BFX_CHANALL; return p
	def chorus_wide(self):
		p = BASS_BFX_CHORUS(); p.fDryMix, p.fWetMix, p.fFeedback, p.fMinSweep, p.fMaxSweep, p.fRate, p.lChannel = 0.82, 0.55, 0.08, 1.0, 14.0, 0.75, BASS_BFX_CHANALL; return p
	def phaser_robot(self):
		p = BASS_BFX_PHASER(); p.fDryMix, p.fWetMix, p.fFeedback, p.fRate, p.fRange, p.fFreq, p.lChannel = 0.86, 0.52, 0.24, 1.1, 3.2, 900.0, BASS_BFX_CHANALL; return p
	def phaser_slow(self):
		p = BASS_BFX_PHASER(); p.fDryMix, p.fWetMix, p.fFeedback, p.fRate, p.fRange, p.fFreq, p.lChannel = 0.90, 0.36, 0.12, 0.35, 2.2, 700.0, BASS_BFX_CHANALL; return p

	# --- PEAK EQ & BIQUAD FILTERS ---
	def _peakeq(self, band, center, gain, bw=0.0):
		p = BASS_BFX_PEAKEQ(); p.lBand, p.fBandwidth, p.fCenter, p.fGain, p.lChannel = int(band), float(bw), float(center), float(gain), int(BASS_BFX_CHANALL); return p

	def peakeq_bass_boost(self): return self._peakeq(0, 60.0, 12.0, 1.5)
	def eq_mud_cut(self): return self._peakeq(1, 250.0, -10.0, 1.0)
	def eq_low_mid_scoop(self): return self._peakeq(2, 500.0, -8.0, 1.2)
	def eq_presence_boost(self): return self._peakeq(3, 3500.0, 9.0, 0.8)
	def eq_air_highs(self): return self._peakeq(4, 12000.0, 10.0, 1.2)

	def _bqf(self, kind, center, gain=0.0, bandwidth=0.0, q=0.707, slope=0.707):
		p = BASS_BFX_BQF(); p.lFilter, p.fCenter, p.fGain, p.fBandwidth, p.fQ, p.fS, p.lChannel = int(kind), float(center), float(gain), float(bandwidth), float(q), float(slope), int(BASS_BFX_CHANALL); return p

	def bqf_lowpass_wall(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 350.0, q=0.5)
	def lowpass_wall_soft(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 800.0, q=0.6)
	def lpf_underwater(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 400.0, q=2.5)
	def lpf_muffled_neighbor(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 600.0, q=0.8)
	def lowpass_dark(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 1200.0, q=0.707)
	def lowpass_voice_muffle(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 900.0, q=0.707)
	def bqf_bandpass_phone(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 1200.0, q=2.5)
	def megaphone_extreme(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 2500.0, q=3.5)
	def bandpass_walkie_talkie(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 1800.0, q=4.0)
	def bandpass_radio(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 2000.0, q=2.0)
	def bandpass_voice(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 1000.0, q=1.0)
	def bqf_highpass_radio(self): return self._bqf(BASS_BFX_BQF_HIGHPASS, 900.0, q=1.0)
	def hpf_crystal_clear(self): return self._bqf(BASS_BFX_BQF_HIGHPASS, 2500.0, q=0.8)
	def highpass_rumble_cut(self): return self._bqf(BASS_BFX_BQF_HIGHPASS, 120.0, q=1.5)
	def highpass_light(self): return self._bqf(BASS_BFX_BQF_HIGHPASS, 300.0, q=0.707)
	def bqf_notch_60hz(self): return self._bqf(BASS_BFX_BQF_NOTCH, 60.0, q=4.0)
	def bqf_peaking_mid(self): return self._bqf(BASS_BFX_BQF_PEAKINGEQ, 1000.0, gain=8.0, q=1.0)
	def allpass_phase(self): return self._bqf(BASS_BFX_BQF_ALLPASS, 1200.0, q=1.5)
	def low_shelf_warm(self): return self._bqf(BASS_BFX_BQF_LOWSHELF, 200.0, gain=8.0, slope=1.0)
	def low_shelf_dark(self): return self._bqf(BASS_BFX_BQF_LOWSHELF, 300.0, gain=-12.0, slope=1.0)
	def high_shelf_air(self): return self._bqf(BASS_BFX_BQF_HIGHSHELF, 5000.0, gain=9.0, slope=1.0)
	def high_shelf_dark(self): return self._bqf(BASS_BFX_BQF_HIGHSHELF, 4000.0, gain=-15.0, slope=1.0)
	def presence_clarity(self): return self._bqf(BASS_BFX_BQF_PEAKINGEQ, 3200.0, gain=10.0, q=1.5)
	def treble_sparkle(self): return self._bqf(BASS_BFX_BQF_PEAKINGEQ, 8000.0, gain=8.0, q=1.5)
	def mud_reduction(self): return self._bqf(BASS_BFX_BQF_PEAKINGEQ, 280.0, gain=-10.0, q=1.2)
	def boxiness_cut(self): return self._bqf(BASS_BFX_BQF_PEAKINGEQ, 500.0, gain=-8.0, q=1.0)
	def sub_bass_rumble(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 80.0, q=1.0)

	def parse_fx_string(self, fx_str):
		# Parse dynamic colon-separated FX strings like sound.cpp (e.g. "$id:reverb:0:-10:1000:0.5")
		args = [a for a in fx_str.split(":") if a != ""]
		if not args: return None, None, None
		fx_id = args.pop(0) if args[0].startswith("$") else ""
		if not args: return fx_id, None, None
		cmd, f = args[0], [float(x) for x in args[1:]]
		if cmd == "reverb" and len(f) >= 4: return fx_id, BASS_FX_DX8_REVERB, self._dx8_reverb(f[0], f[1], f[2], f[3])
		if cmd in ("lowpass", "highpass", "bandpass") and len(f) >= 3:
			k = {"lowpass": BASS_BFX_BQF_LOWPASS, "highpass": BASS_BFX_BQF_HIGHPASS, "bandpass": BASS_BFX_BQF_BANDPASS}[cmd]
			return fx_id, BASS_FX_BFX_BQF, self._bqf(k, f[0], 0.0, f[1], f[2], 0.0)
		if cmd == "freeverb" and len(f) >= 5:
			p = BASS_BFX_FREEVERB(); p.fDryMix, p.fWetMix, p.fRoomSize, p.fDamp, p.fWidth, p.lMode, p.lChannel = f[0], f[1], f[2], f[3], f[4], (1 if len(f) > 5 and f[5] == 1 else 0), -1
			return fx_id, BASS_FX_BFX_FREEVERB, p
		if cmd == "pitchshift" and len(f) >= 1:
			p = BASS_BFX_PITCHSHIFT(); p.fPitchShift, p.fSemitones, p.lFFTsize, p.lOsamp, p.lChannel = f[0], (f[1] if len(f) > 1 else 0.0), 2048, 16, -1
			return fx_id, BASS_FX_BFX_PITCHSHIFT, p
		return fx_id, None, None