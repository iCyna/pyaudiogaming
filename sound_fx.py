# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Unified Audio FX Engine: BASS DX8, BASS_FX (BFX), and Steam Audio (BASS_HRTF) Presets & Parameter Manager.

import math
from .sound_modules.pybass import *
from .sound_modules.pybass_fx import *
from .sound_modules import pybass_hrtf as hrtf_mod

# Map friendly parameter names to ctypes structure field names for BASS_FX / DX8
_STRUCT_PARAM_ALIASES = {
	"in_gain": "fInGain",
	"reverb_mix": "fReverbMix",
	"reverb_time": "fReverbTime",
	"hf_ratio": "fHighFreqRTRatio",
	"wet_dry": ("fWetDry", "fWetDryMix"),
	"wet": ("fWetMix", "fWetDry", "fWetDryMix", "fReverbMix", "fLevel"),
	"dry": "fDryMix",
	"speed": "fSpeed",
	"drive": "fDrive",
	"feedback": "fFeedback",
	"volume": "fVolume",
	"gain": ("fGain", "fInGain"),
	"threshold": "fThreshold",
	"ratio": "fRatio",
	"attack": ("fAttack", "fAttacktime"),
	"release": ("fRelease", "fReleasetime"),
	"min_sweep": "fMinSweep",
	"max_sweep": "fMaxSweep",
	"rate": "fRate",
	"range": "fRange",
	"freq": ("fFreq", "fFrequency", "fCenter", "fCutOffFreq"),
	"center": ("fCenter", "fCutOffFreq", "fFrequency", "fFreq"),
	"bandwidth": "fBandwidth",
	"q": "fQ",
	"slope": "fS",
	"filter": "lFilter",
	"band": "lBand",
	"delay": ("fDelay", "lDelay"),
	"left_delay": "fLeftDelay",
	"right_delay": "fRightDelay",
	"room_size": "fRoomSize",
	"damp": "fDamp",
	"width": "fWidth",
	"mode": ("lMode", "fMode"),
	"pitch_shift": "fPitchShift",
	"semitones": "fSemitones",
	"fft_size": "lFFTsize",
	"osamp": "lOsamp",
	"resonance": "fResonance",
	"cutoff": "fCutOffFreq",
	"channel": "lChannel",
}

# Map friendly parameter names to Steam Audio BASS_HRTF_PARAM_* IDs
STEAM_PARAM_MAP = {
	"occlusion": hrtf_mod.BASS_HRTF_PARAM_OCCLUSION,
	"occ": hrtf_mod.BASS_HRTF_PARAM_OCCLUSION,
	"spatial_blend": hrtf_mod.BASS_HRTF_PARAM_SPATIAL_BLEND,
	"blend": hrtf_mod.BASS_HRTF_PARAM_SPATIAL_BLEND,
	"gain": hrtf_mod.BASS_HRTF_PARAM_GAIN,
	"air_absorption": hrtf_mod.BASS_HRTF_PARAM_AIR_ABSORPTION,
	"air": hrtf_mod.BASS_HRTF_PARAM_AIR_ABSORPTION,
	"directivity": hrtf_mod.BASS_HRTF_PARAM_DIRECTIVITY,
	"dipole_weight": hrtf_mod.BASS_HRTF_PARAM_DIRECTIVITY_WEIGHT,
	"directivity_weight": hrtf_mod.BASS_HRTF_PARAM_DIRECTIVITY_WEIGHT,
	"dipole_power": hrtf_mod.BASS_HRTF_PARAM_DIRECTIVITY_POWER,
	"directivity_power": hrtf_mod.BASS_HRTF_PARAM_DIRECTIVITY_POWER,
	"source_radius": hrtf_mod.BASS_HRTF_PARAM_SOURCE_RADIUS,
	"radius": hrtf_mod.BASS_HRTF_PARAM_SOURCE_RADIUS,
	"trans_low": hrtf_mod.BASS_HRTF_PARAM_TRANS_LOW,
	"trans_mid": hrtf_mod.BASS_HRTF_PARAM_TRANS_MID,
	"trans_high": hrtf_mod.BASS_HRTF_PARAM_TRANS_HIGH,
	"reverb_low": hrtf_mod.BASS_HRTF_PARAM_REVERB_LOW,
	"reverb_mid": hrtf_mod.BASS_HRTF_PARAM_REVERB_MID,
	"reverb_high": hrtf_mod.BASS_HRTF_PARAM_REVERB_HIGH,
	"reverb_eq_low": hrtf_mod.BASS_HRTF_PARAM_REVERB_EQ_LOW,
	"reverb_eq_mid": hrtf_mod.BASS_HRTF_PARAM_REVERB_EQ_MID,
	"reverb_eq_high": hrtf_mod.BASS_HRTF_PARAM_REVERB_EQ_HIGH,
	"reverb_delay_ms": hrtf_mod.BASS_HRTF_PARAM_REVERB_DELAY_MS,
	"delay_ms": hrtf_mod.BASS_HRTF_PARAM_REVERB_DELAY_MS,
	"reverb_wet": hrtf_mod.BASS_HRTF_PARAM_REVERB_WET,
	"wet": hrtf_mod.BASS_HRTF_PARAM_REVERB_WET,
	"path_eq_low": hrtf_mod.BASS_HRTF_PARAM_PATH_EQ_LOW,
	"path_eq_mid": hrtf_mod.BASS_HRTF_PARAM_PATH_EQ_MID,
	"path_eq_high": hrtf_mod.BASS_HRTF_PARAM_PATH_EQ_HIGH,
	"path_wet": hrtf_mod.BASS_HRTF_PARAM_PATH_WET,
	"ambi_order": hrtf_mod.BASS_HRTF_PARAM_AMBI_ORDER,
	"order": hrtf_mod.BASS_HRTF_PARAM_AMBI_ORDER,
	"surround_layout": hrtf_mod.BASS_HRTF_PARAM_SURROUND_LAYOUT,
	"layout": hrtf_mod.BASS_HRTF_PARAM_SURROUND_LAYOUT,
	"interpolation": hrtf_mod.BASS_HRTF_PARAM_INTERPOLATION,
	"bilinear": hrtf_mod.BASS_HRTF_PARAM_INTERPOLATION,
	"low_latency_flush": hrtf_mod.BASS_HRTF_PARAM_LOW_LATENCY_FLUSH,
}


class Basic:
	"""Central BASS_FX, DX8, and Steam Audio preset collection & dynamic string FX parser."""
	def __init__(self):
		BASS_FX_GetVersion()
		self.fxs = {
			# DX8 Reverbs
			"large room": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.large_room},
			"small room": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.small_room},
			"hall": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.hall},
			"long hallway": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.long_hallway},
			"city": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.city},
			"bedroom": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.bedroom},
			"cave": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.cave},
			"concert_arena": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.concert_arena},
			"bathroom": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.bathroom},
			"studio_vocal_booth": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.studio_vocal_booth},
			"canyon": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.canyon},
			"hallway_bright": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.hallway_bright},
			"hallway_dark": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.hallway_dark},
			"city_open": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.city_open},
			"city_narrow": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.city_narrow},
			"warehouse": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.warehouse},
			"stone_room": {"engine": "bass", "name": BASS_FX_DX8_REVERB, "param": self.stone_room},

			# Freeverb (BASS_FX)
			"freeverb_room": {"engine": "bass", "name": BASS_FX_BFX_FREEVERB, "param": self.freeverb_room},
			"freeverb_hall": {"engine": "bass", "name": BASS_FX_BFX_FREEVERB, "param": self.freeverb_hall},
			"freeverb_cathedral": {"engine": "bass", "name": BASS_FX_BFX_FREEVERB, "param": self.freeverb_cathedral},
			"freeverb_plate": {"engine": "bass", "name": BASS_FX_BFX_FREEVERB, "param": self.freeverb_plate},

			# Echo / Delay (DX8 & BASS_FX)
			"echo_short": {"engine": "bass", "name": BASS_FX_DX8_ECHO, "param": self.echo_short},
			"echo_canyon": {"engine": "bass", "name": BASS_FX_DX8_ECHO, "param": self.echo_canyon},
			"echo_slapback": {"engine": "bass", "name": BASS_FX_DX8_ECHO, "param": self.echo_slapback},
			"echo2_stereo": {"engine": "bass", "name": BASS_FX_BFX_ECHO2, "param": self.echo2_stereo},
			"echo2_dub": {"engine": "bass", "name": BASS_FX_BFX_ECHO2, "param": self.echo2_dub},
			"echo3_pingpong": {"engine": "bass", "name": BASS_FX_BFX_ECHO3, "param": self.echo3_pingpong},

			# Modulation / Distortion / Dynamics / Pitch
			"flanger_space": {"engine": "bass", "name": BASS_FX_BFX_FLANGER, "param": self.flanger_space},
			"flanger_tunnel": {"engine": "bass", "name": BASS_FX_BFX_FLANGER, "param": self.flanger_tunnel},
			"radio_distortion": {"engine": "bass", "name": BASS_FX_BFX_DISTORTION, "param": self.radio_distortion},
			"telephone_distortion": {"engine": "bass", "name": BASS_FX_BFX_DISTORTION, "param": self.telephone_distortion},
			"vinyl_lofi": {"engine": "bass", "name": BASS_FX_BFX_DISTORTION, "param": self.vinyl_lofi},
			"studio_compressor": {"engine": "bass", "name": BASS_FX_BFX_COMPRESSOR2, "param": self.studio_compressor},
			"voice_leveler": {"engine": "bass", "name": BASS_FX_BFX_COMPRESSOR2, "param": self.voice_leveler},
			"hard_limiter": {"engine": "bass", "name": BASS_FX_BFX_COMPRESSOR2, "param": self.hard_limiter},
			"chorus_ensemble": {"engine": "bass", "name": BASS_FX_BFX_CHORUS, "param": self.chorus_ensemble},
			"chorus_wide": {"engine": "bass", "name": BASS_FX_BFX_CHORUS, "param": self.chorus_wide},
			"phaser_robot": {"engine": "bass", "name": BASS_FX_BFX_PHASER, "param": self.phaser_robot},
			"phaser_slow": {"engine": "bass", "name": BASS_FX_BFX_PHASER, "param": self.phaser_slow},
			"autowah_funk": {"engine": "bass", "name": BASS_FX_BFX_AUTOWAH, "param": self.autowah_funk},
			"autowah_synth": {"engine": "bass", "name": BASS_FX_BFX_AUTOWAH, "param": self.autowah_synth},
			"damp_autogain": {"engine": "bass", "name": BASS_FX_BFX_DAMP, "param": self.damp_autogain},
			"apf_diffuser": {"engine": "bass", "name": BASS_FX_BFX_APF, "param": self.apf_diffuser},
			"gargle_tremolo": {"engine": "bass", "name": BASS_FX_DX8_GARGLE, "param": self.gargle_tremolo},
			"gargle_cyber": {"engine": "bass", "name": BASS_FX_DX8_GARGLE, "param": self.gargle_cyber},
			"pitch_monster": {"engine": "bass", "name": BASS_FX_BFX_PITCHSHIFT, "param": self.pitch_monster},
			"pitch_chipmunk": {"engine": "bass", "name": BASS_FX_BFX_PITCHSHIFT, "param": self.pitch_chipmunk},
			"pitch_deep_voice": {"engine": "bass", "name": BASS_FX_BFX_PITCHSHIFT, "param": self.pitch_deep_voice},
		}

		self.filters = {
			"underwater": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.lpf_underwater},
			"muffled_wall": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.bqf_lowpass_wall},
			"muffled_neighbor": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.lpf_muffled_neighbor},
			"telephone_line": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.bqf_bandpass_phone},
			"radio": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.bandpass_radio},
			"megaphone": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.megaphone_extreme},
			"subwoofer_boost": {"engine": "bass", "name": BASS_FX_BFX_PEAKEQ, "param": self.peakeq_bass_boost},
			"voice_clarity": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.presence_clarity},
			"distant_thin": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.highpass_light},
			"lowshelf_warm": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.bqf_lowshelf_warm},
			"highshelf_air": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.bqf_highshelf_air},
			"notch_hum": {"engine": "bass", "name": BASS_FX_BFX_BQF, "param": self.bqf_notch_hum},
		}

		# Steam Audio (Phonon / BASS_HRTF) Native Effects Catalog
		self.steam_fxs = {
			# 1. Steam Audio Parametric Reflection / Reverb Rooms
			"steam_small_room": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_SMALL_ROOM, "params": {}},
			"steam_medium_room": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_MEDIUM_ROOM, "params": {}},
			"steam_large_room": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_LARGE_ROOM, "params": {}},
			"steam_hall": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_HALL, "params": {}},
			"steam_long_hallway": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_LONG_HALLWAY, "params": {}},
			"steam_cave": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_CAVE, "params": {}},
			"steam_canyon": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_CANYON, "params": {}},
			"steam_bathroom": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_BATHROOM, "params": {}},
			"steam_warehouse": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_WAREHOUSE, "params": {}},
			"steam_tunnel": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_TUNNEL, "params": {}},
			"steam_forest": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_FOREST, "params": {}},
			"steam_city": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_CITY, "params": {}},
			"steam_underwater": {
				"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_UNDERWATER,
				"extra_fx": [(hrtf_mod.BASS_HRTF_FX_DIRECT, hrtf_mod.BASS_HRTF_MAT_CARPET)],
				"params": {"occlusion": 0.85, "trans_low": 0.65, "trans_mid": 0.12, "trans_high": 0.01, "air_absorption": 3.5}
			},
			"steam_bunker": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_BUNKER, "params": {}},
			"steam_studio": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_STUDIO, "params": {}},
			"steam_arena": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": hrtf_mod.BASS_HRTF_REVERB_ARENA, "params": {}},

			# 2. Steam Audio Direct Physical & Material Transmission / Occlusion FX
			"steam_direct_air": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_AIR, "params": {"occlusion": 0.0, "air_absorption": 1.0}},
			"steam_wall_generic": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_GENERIC, "params": {"occlusion": 0.70}},
			"steam_wall_brick": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_BRICK, "params": {"occlusion": 0.82}},
			"steam_wall_concrete": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_CONCRETE, "params": {"occlusion": 0.90}},
			"steam_wall_ceramic": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_CERAMIC, "params": {"occlusion": 0.65}},
			"steam_wall_gravel": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_GRAVEL, "params": {"occlusion": 0.75}},
			"steam_wall_carpet": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_CARPET, "params": {"occlusion": 0.60}},
			"steam_wall_glass": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_GLASS, "params": {"occlusion": 0.55}},
			"steam_wall_plaster": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_PLASTER, "params": {"occlusion": 0.62}},
			"steam_wall_wood": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_WOOD, "params": {"occlusion": 0.68}},
			"steam_wall_metal": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_METAL, "params": {"occlusion": 0.78}},
			"steam_wall_rock": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_ROCK, "params": {"occlusion": 0.92}},
			"steam_distant_air": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_AIR, "params": {"occlusion": 0.15, "air_absorption": 4.0}},
			"steam_megaphone_cone": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": hrtf_mod.BASS_HRTF_MAT_AIR, "params": {"dipole_weight": 0.85, "dipole_power": 2.5}},

			# 3. Steam Audio Multi-Path Propagation FX
			"steam_pathing_corridor": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_PATHING, "preset_id": 0, "params": {"path_eq_low": 0.95, "path_eq_mid": 0.80, "path_eq_high": 0.55, "path_wet": 0.35}},
			"steam_pathing_corner": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_PATHING, "preset_id": 0, "params": {"path_eq_low": 0.85, "path_eq_mid": 0.50, "path_eq_high": 0.20, "path_wet": 0.45}},
			"steam_pathing_muffled_vent": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_PATHING, "preset_id": 0, "params": {"path_eq_low": 0.70, "path_eq_mid": 0.35, "path_eq_high": 0.08, "path_wet": 0.50}},

			# 4. Steam Audio Virtual Surround, Ambisonics & Panning FX
			"steam_virtual_surround": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_VIRTUAL_SURROUND, "preset_id": hrtf_mod.BASS_HRTF_LAYOUT_STEREO, "params": {}},
			"steam_virtual_surround_quad": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_VIRTUAL_SURROUND, "preset_id": hrtf_mod.BASS_HRTF_LAYOUT_QUAD, "params": {}},
			"steam_virtual_surround_5_1": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_VIRTUAL_SURROUND, "preset_id": hrtf_mod.BASS_HRTF_LAYOUT_SURROUND_5_1, "params": {}},
			"steam_virtual_surround_7_1": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_VIRTUAL_SURROUND, "preset_id": hrtf_mod.BASS_HRTF_LAYOUT_SURROUND_7_1, "params": {}},
			"steam_ambisonics": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_AMBISONICS, "preset_id": 1, "params": {"ambi_order": 1}},
			"steam_ambisonics_2nd": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_AMBISONICS, "preset_id": 2, "params": {"ambi_order": 2}},
			"steam_ambisonics_3rd": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_AMBISONICS, "preset_id": 3, "params": {"ambi_order": 3}},
			"steam_panning": {"engine": "steam", "fx_type": hrtf_mod.BASS_HRTF_FX_PANNING, "preset_id": 0, "params": {}},
		}

	def get_fx(self, fx_key):
		"""Resolve an FX preset by key from fxs, filters, steam_fxs, or dynamic colon string."""
		if not isinstance(fx_key, str):
			return None
		k = fx_key.strip()
		k_low = k.lower()
		target = (
			self.fxs.get(k) or self.fxs.get(k_low)
			or self.filters.get(k) or self.filters.get(k_low)
			or self.steam_fxs.get(k) or self.steam_fxs.get(k_low)
		)
		if target is not None:
			return target
		if ":" in k:
			parsed = self.parse_fx_string(k)
			if parsed and parsed[1] is not None:
				fx_id, fx_name_or_dict, param_obj = parsed
				if isinstance(fx_name_or_dict, dict):
					return fx_name_or_dict
				return {"engine": "bass", "id": fx_id, "name": fx_name_or_dict, "param": lambda: param_obj}
		return None

	def apply_param_overrides(self, param_obj, **overrides):
		"""Update fields on an existing BASS_FX / DX8 ctypes structure without recreating the FX."""
		if param_obj is None or not overrides:
			return param_obj
		field_types = dict(getattr(param_obj, "_fields_", ()))
		for key, val in overrides.items():
			if val is None:
				continue
			candidates = _STRUCT_PARAM_ALIASES.get(key.lower(), key)
			if isinstance(candidates, str):
				candidates = (candidates, key)
			else:
				candidates = tuple(candidates) + (key,)
			for field_name in candidates:
				if field_name in field_types:
					ftype = field_types[field_name]
					if ftype in (ctypes.c_int, ctypes.c_int32, ctypes.c_uint32, ctypes.c_long, ctypes.c_ulong):
						setattr(param_obj, field_name, int(val))
					elif ftype is ctypes.c_bool:
						setattr(param_obj, field_name, bool(val))
					else:
						setattr(param_obj, field_name, float(val))
					break
		return param_obj

	def resolve_steam_param_id(self, param_name):
		if isinstance(param_name, int):
			return param_name
		return STEAM_PARAM_MAP.get(str(param_name).strip().lower())

	# --- DX8 REVERB & ECHO & GARGLE PRESETS ---
	def _dx8_reverb(self, in_gain=0.0, reverb_mix=-10.0, reverb_time=1000.0, hf_ratio=0.001):
		p = BASS_DX8_REVERB()
		p.fInGain, p.fReverbMix, p.fReverbTime, p.fHighFreqRTRatio = float(in_gain), float(reverb_mix), float(reverb_time), float(hf_ratio)
		return p

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

	def _dx8_echo(self, wet_dry=35.0, feedback=35.0, left_delay=250.0, right_delay=250.0, pan_delay=0):
		p = BASS_DX8_ECHO()
		p.fWetDryMix, p.fFeedback, p.fLeftDelay, p.fRightDelay, p.lPanDelay = float(wet_dry), float(feedback), float(left_delay), float(right_delay), int(pan_delay)
		return p

	def echo_short(self): return self._dx8_echo(28.0, 22.0, 120.0, 140.0, 0)
	def echo_canyon(self): return self._dx8_echo(45.0, 55.0, 420.0, 480.0, 1)
	def echo_slapback(self): return self._dx8_echo(30.0, 10.0, 75.0, 75.0, 0)

	def gargle_tremolo(self):
		p = BASS_DX8_GARGLE(); p.dwRateHz, p.dwWaveShape = 8, 0; return p
	def gargle_cyber(self):
		p = BASS_DX8_GARGLE(); p.dwRateHz, p.dwWaveShape = 45, 1; return p

	# --- FREEVERB & ECHO2/3 (BASS_FX) ---
	def _freeverb(self, dry=1.0, wet=0.35, room_size=0.65, damp=0.45, width=1.0, mode=0):
		p = BASS_BFX_FREEVERB()
		p.fDryMix, p.fWetMix, p.fRoomSize, p.fDamp, p.fWidth, p.fMode, p.lChannel = float(dry), float(wet), float(room_size), float(damp), float(width), float(mode), float(BASS_BFX_CHANALL)
		return p

	def freeverb_room(self): return self._freeverb(1.0, 0.25, 0.45, 0.55, 1.0)
	def freeverb_hall(self): return self._freeverb(0.95, 0.42, 0.78, 0.35, 1.0)
	def freeverb_cathedral(self): return self._freeverb(0.88, 0.58, 0.92, 0.22, 1.0)
	def freeverb_plate(self): return self._freeverb(0.95, 0.35, 0.62, 0.15, 1.0)

	def echo2_stereo(self):
		p = BASS_BFX_ECHO2(); p.fDryMix, p.fWetMix, p.fFeedback, p.fDelay, p.lChannel = 0.95, 0.38, 0.35, 0.28, BASS_BFX_CHANALL; return p
	def echo2_dub(self):
		p = BASS_BFX_ECHO2(); p.fDryMix, p.fWetMix, p.fFeedback, p.fDelay, p.lChannel = 0.90, 0.50, 0.62, 0.42, BASS_BFX_CHANALL; return p
	def echo3_pingpong(self):
		p = BASS_BFX_ECHO3(); p.fDryMix, p.fWetMix, p.fDelay, p.lChannel = 0.92, 0.45, 0.32, BASS_BFX_CHANALL; return p

	# --- MODULATION / DISTORTION / DYNAMICS / PITCH ---
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
	def autowah_funk(self):
		p = BASS_BFX_AUTOWAH(); p.fDryMix, p.fWetMix, p.fFeedback, p.fRate, p.fRange, p.fFreq, p.lChannel = 0.50, 1.20, 0.35, 2.2, 4.0, 350.0, BASS_BFX_CHANALL; return p
	def autowah_synth(self):
		p = BASS_BFX_AUTOWAH(); p.fDryMix, p.fWetMix, p.fFeedback, p.fRate, p.fRange, p.fFreq, p.lChannel = 0.65, 0.95, 0.45, 0.8, 5.5, 220.0, BASS_BFX_CHANALL; return p
	def damp_autogain(self):
		p = BASS_BFX_DAMP(); p.fTarget, p.fQuiet, p.fRate, p.fGain, p.fDelay, p.lChannel = 0.92, 0.03, 0.02, 1.0, 0.2, BASS_BFX_CHANALL; return p
	def apf_diffuser(self):
		p = BASS_BFX_APF(); p.fGain, p.fDelay, p.lChannel = 0.60, 0.035, BASS_BFX_CHANALL; return p

	def _pitchshift(self, shift=1.0, semitones=0.0, fft_size=1024, osamp=8):
		p = BASS_BFX_PITCHSHIFT()
		p.fPitchShift, p.fSemitones, p.lFFTsize, p.lOsamp, p.lChannel = float(shift), float(semitones), int(fft_size), int(osamp), BASS_BFX_CHANALL
		return p

	def pitch_monster(self): return self._pitchshift(1.0, -7.0, 1024, 8)
	def pitch_chipmunk(self): return self._pitchshift(1.0, 6.0, 1024, 8)
	def pitch_deep_voice(self): return self._pitchshift(1.0, -3.5, 1024, 8)

	# --- PEAK EQ & BIQUAD FILTERS ---
	def _peakeq(self, band, center, gain, bw=0.0):
		p = BASS_BFX_PEAKEQ(); p.lBand, p.fBandwidth, p.fCenter, p.fGain, p.lChannel = int(band), float(bw), float(center), float(gain), int(BASS_BFX_CHANALL); return p

	def peakeq_bass_boost(self): return self._peakeq(0, 65.0, 10.0, 1.5)

	def _bqf(self, kind, center, gain=0.0, bandwidth=0.0, q=0.707, slope=0.707):
		p = BASS_BFX_BQF(); p.lFilter, p.fCenter, p.fGain, p.fBandwidth, p.fQ, p.fS, p.lChannel = int(kind), float(center), float(gain), float(bandwidth), float(q), float(slope), int(BASS_BFX_CHANALL); return p

	def bqf_lowpass_wall(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 420.0, q=0.6)
	def lpf_underwater(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 650.0, q=0.707)
	def lpf_muffled_neighbor(self): return self._bqf(BASS_BFX_BQF_LOWPASS, 700.0, q=0.707)
	def bqf_bandpass_phone(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 1200.0, q=2.0)
	def megaphone_extreme(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 2200.0, q=2.2)
	def bandpass_radio(self): return self._bqf(BASS_BFX_BQF_BANDPASS, 1800.0, q=1.8)
	def highpass_light(self): return self._bqf(BASS_BFX_BQF_HIGHPASS, 500.0, q=0.707)
	def presence_clarity(self): return self._bqf(BASS_BFX_BQF_PEAKINGEQ, 3200.0, gain=8.0, q=1.2)
	def bqf_lowshelf_warm(self): return self._bqf(BASS_BFX_BQF_LOWSHELF, 180.0, gain=5.5, slope=0.707)
	def bqf_highshelf_air(self): return self._bqf(BASS_BFX_BQF_HIGHSHELF, 6500.0, gain=4.5, slope=0.707)
	def bqf_notch_hum(self): return self._bqf(BASS_BFX_BQF_NOTCH, 60.0, bandwidth=0.25)

	def parse_fx_string(self, fx_str):
		"""Parse dynamic colon-separated FX strings (both BASS_FX and Steam Audio)."""
		args = [a for a in fx_str.split(":") if a != ""]
		if not args: return None, None, None
		fx_id = args.pop(0) if args[0].startswith("$") else ""
		if not args: return fx_id, None, None
		cmd = args[0].lower()
		f = []
		for x in args[1:]:
			try: f.append(float(x))
			except ValueError: pass

		if cmd == "reverb" and len(f) >= 4:
			return fx_id, BASS_FX_DX8_REVERB, self._dx8_reverb(f[0], f[1], f[2], f[3])
		if cmd in ("lowpass", "highpass", "bandpass", "notch", "peakingeq", "lowshelf", "highshelf") and len(f) >= 2:
			k_map = {
				"lowpass": BASS_BFX_BQF_LOWPASS, "highpass": BASS_BFX_BQF_HIGHPASS,
				"bandpass": BASS_BFX_BQF_BANDPASS, "notch": BASS_BFX_BQF_NOTCH,
				"peakingeq": BASS_BFX_BQF_PEAKINGEQ, "lowshelf": BASS_BFX_BQF_LOWSHELF,
				"highshelf": BASS_BFX_BQF_HIGHSHELF
			}
			center = f[0]
			gain = f[1] if cmd in ("peakingeq", "lowshelf", "highshelf") else 0.0
			bw = f[1] if cmd not in ("peakingeq", "lowshelf", "highshelf") and len(f) >= 3 else 0.0
			q = f[2] if len(f) >= 3 else (f[1] if cmd not in ("peakingeq", "lowshelf", "highshelf") else 0.707)
			return fx_id, BASS_FX_BFX_BQF, self._bqf(k_map[cmd], center, gain, bw, q, 0.707)
		if cmd == "freeverb" and len(f) >= 5:
			return fx_id, BASS_FX_BFX_FREEVERB, self._freeverb(f[0], f[1], f[2], f[3], f[4], (1 if len(f) > 5 and f[5] == 1 else 0))
		if cmd == "pitchshift" and len(f) >= 1:
			return fx_id, BASS_FX_BFX_PITCHSHIFT, self._pitchshift(f[0], (f[1] if len(f) > 1 else 0.0), 1024, 8)
		if cmd == "echo" and len(f) >= 4:
			return fx_id, BASS_FX_DX8_ECHO, self._dx8_echo(f[0], f[1], f[2], f[3], (int(f[4]) if len(f) > 4 else 0))
		if cmd == "steam_reverb":
			params = {}
			if len(f) >= 3:
				params["reverb_low"], params["reverb_mid"], params["reverb_high"] = f[0], f[1], f[2]
			if len(f) >= 6:
				params["reverb_eq_low"], params["reverb_eq_mid"], params["reverb_eq_high"] = f[3], f[4], f[5]
			if len(f) >= 7:
				params["reverb_delay_ms"] = f[6]
			if len(f) >= 8:
				params["reverb_wet"] = f[7]
			desc = {"engine": "steam", "id": fx_id or "steam_reverb", "fx_type": hrtf_mod.BASS_HRTF_FX_REFLECTION, "preset_id": -1, "params": params}
			return fx_id, desc, params
		if cmd == "steam_direct":
			params = {}
			if len(f) >= 1: params["occlusion"] = f[0]
			if len(f) >= 2: params["air_absorption"] = f[1]
			if len(f) >= 5: params["trans_low"], params["trans_mid"], params["trans_high"] = f[2], f[3], f[4]
			desc = {"engine": "steam", "id": fx_id or "steam_direct", "fx_type": hrtf_mod.BASS_HRTF_FX_DIRECT, "preset_id": -1, "params": params}
			return fx_id, desc, params
		if cmd == "steam_path":
			params = {}
			if len(f) >= 3: params["path_eq_low"], params["path_eq_mid"], params["path_eq_high"] = f[0], f[1], f[2]
			if len(f) >= 4: params["path_wet"] = f[3]
			desc = {"engine": "steam", "id": fx_id or "steam_path", "fx_type": hrtf_mod.BASS_HRTF_FX_PATHING, "preset_id": 0, "params": params}
			return fx_id, desc, params
		return fx_id, None, None
