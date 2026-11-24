# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Screen reader and TTS speech output wrapper with per-engine profiles.
# Supports Windows, Linux, macOS, Android, and iOS.

from .g2access import Auto, Router

class Speech:
	def __init__(self):
		self.speech=Auto()
		self.speech_history = []
		self.history_index = -1

	def say(self, text, i=True, split=False):
		"""tts speech"""
		saying = False
		string = text
		if isinstance(text, str): 
			saying = True
		elif isinstance(text, list) and split:
			for string in text:
				if string is None or string == "": continue
				string = str(string)
				self.speech.output(string, interrupt=i)
				i = False
				self.speech_history.append(string)
				self.history_index = len(self.speech_history)
			return
		elif isinstance(text, list) and not split:
			string = ""
			for text in text: string += text
			saying = True

		if saying and string is not None and string != "":
			string = str(string)
			self.speech.output(string, interrupt=i)
			self.speech_history.append(string)
			self.history_index = len(self.speech_history)

	def saync(self, string, i=True):
		"""tts speech no log"""
		self.speech.output(str(string), interrupt=i)

	def say3d(self, text, lx, ly, lz, sx, sy, sz, i=True, **kwargs):
		if text is None or text == "":
			return
		string = str(text)
		self.speech.speak3d(string, lx, ly, lz, sx, sy, sz, interrupt=i, **kwargs)
		self.speech_history.append(string)
		self.history_index = len(self.speech_history)

	speech3d = say3d

	def get_speech_volume(self): return self.speech.get_volume()
	def set_speech_volume(self, value): return self.speech.set_volume(value)
	def get_speech_pitch(self): return self.speech.get_pitch()
	def set_speech_pitch(self, value): return self.speech.set_pitch(value)
	def get_speech_rate(self): return self.speech.get_rate()
	def set_speech_rate(self, value): return self.speech.set_rate(value)
	def get_speech_voice(self): return self.speech.get_voice()
	def set_speech_voice(self, type): return self.speech.set_voice(type)
	def get_speech_pan(self): return self.speech.get_pan()
	def set_speech_pan(self, value): return self.speech.set_pan(value)
	def get_speech_sound_pitch(self): return self.speech.get_sound_pitch()
	def set_speech_sound_pitch(self, value): return self.speech.set_sound_pitch(value)
	def get_speech_output_device(self): return self.speech.get_output_device()
	def set_speech_output_device(self, device): return self.speech.set_output_device(device)
	def get_speech_sound(self): return self.speech.get_sound()
	def get_speech_mono(self): return self.speech.get_mono()
	def set_speech_mono(self, value): return self.speech.set_mono(value)
	def get_speech_hrtf(self): return self.speech.get_hrtf()
	def set_speech_hrtf(self, value): return self.speech.set_hrtf(value)
	def get_speech_fx(self): return self.speech.get_fx()
	def set_speech_fx(self, value): return self.speech.set_fx(value)
	def set_speech_zone_fx_provider(self, provider): return self.speech.set_zone_fx_provider(provider)
	def list_speech_fx(self): return self.speech.list_fx()
	def get_speech_auto_pause(self): return self.speech.get_auto_pause()
	def set_speech_auto_pause(self, enabled): return self.speech.set_auto_pause(enabled)
	def list_voices(self): return self.speech.list_voices()
	get_speech_voices = list_voices
	def list_engines(self): return self.speech.list_engines()
	def get_speech_engine(self): return self.speech.get_engine()
	def set_speech_engine(self, value): return self.speech.set_engine(value)
	def list_voice_languages(self): return self.speech.list_voice_languages()
	def get_speech_voice_language(self): return self.speech.get_voice_language()
	def set_speech_voice_language(self, value): return self.speech.set_voice_language(value)
	def get_speech_use_system_default(self): return self.speech.get_use_system_default()
	def set_speech_use_system_default(self, value): return self.speech.set_use_system_default(value)
	def get_outputs(self, active_only=False): return self.speech.get_outputs(active_only=active_only)
	get_screen_readers = get_outputs
	def get_output(self): return self.speech.get_output()
	get_screen_reader = get_output
	def get_active_screen_reader(self): return self.speech.get_active_output()
	def set_output(self, name=None): return self.speech.set_output(name)
	set_screen_reader = set_output
	def get_capabilities(self): return self.speech.get_capabilities()

def say(text, i=True, split=False, log=True):
	from . import buffer
	if not buffer.hspeechwrapper: buffer.hspeechwrapper =Speech()
	if log: buffer.hspeechwrapper.say(text, i=i, split=split)
	else: buffer.hspeechwrapper.saync(text, i=i)
