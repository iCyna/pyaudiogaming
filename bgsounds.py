# -*- coding: utf-8 -*-

import os, glob, concurrent.futures, time, threading, math
import sound_lib
import sound_lib.sample
import sound_lib.output
import sound_lib.stream
from .key import k
from .sound_positioning import *
from .sound_lib.external.pybass import *
from .sound_lib.external.pybass_fx import *
from .bgfx import *

def output():
	o=sound_lib.output.Output()
	return o

class sound(Bgfx):
	def __init__(self):
		super().__init__()
		self.handle = None
		self.freq = 44100
		self.paused = False
		self.boolfadein = False

	def stream(self,filename, draw=False):
		if self.handle:
			self.close()
		if draw:
			self.handle = sound_lib.stream.PushStream(filename)
		else:
			self.handle = sound_lib.stream.FileStream(file=filename)
		self.freq = self.handle.get_frequency()

	def load(self, filename=""):
		if self.handle:
			self.close()
		self.handle = sound_lib.sample.SampleBasedChannel(sound_lib.sample.Sample(filename))
		self.freq = self.handle.get_frequency()

	def sample(self, sample=None):
		if self.handle:
			self.close()
		self.handle = sound_lib.sample.SampleBasedChannel(sample)
		self.freq = self.handle.get_frequency()

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
		# end pause or unpause
	# end setPaused

	def play(self):
		self.handle.looping = False
		if self.boolfadein: self.handle.set_volume(0)
		self.handle.play()

	def play_wait(self):
		self.handle.looping = False
		if self.boolfadein: self.handle.set_volume(0)
		self.handle.play_blocking()

	def play_looped(self):
		self.handle.looping = True
		if self.boolfadein: self.handle.set_volume(0)
		self.handle.play()

	def stop(self):
		if self.handle and self.handle.is_playing:
			self.handle.stop()
			self.handle.set_position(0)

	def fadeout(self, fadetime, value=0, type="volume"):
		if self.handle and self.handle.is_playing:
			self.handle.slide_attribute(type, value, fadetime)

	def fadein(self, fadetime, value=100, type="volume"):
			if self.handle and self.handle.is_playing:
				self.handle.slide_attribute(type, float(value)/100, fadetime)

	def setfx(self, type, priority=0):
		fx_handle = self.handle.set_fx(type["name"], priority=priority)
		params = type["param"]()
		self.handle.set_fx_param(fx_handle, params)

	@property
	def volume(self):
		if not self.handle:
			return False
		return self.handle.get_volume() * 100

	@volume.setter
	def volume(self, value):
		if not self.handle:
			return False
		self.handle.set_volume(float(value) / 100)

	@property
	def pitch(self):
		if not self.handle:
			return False
		return (self.handle.get_frequency() / self.freq) * 100

	@pitch.setter
	def pitch(self, value):
		if not self.handle:
			return False
		self.handle.set_frequency((float(value) / 100) * self.freq)

	@property
	def pan(self):
		if not self.handle:
			return False
		return self.handle.get_pan() * 100

	@pan.setter
	def pan(self, value):
		if not self.handle:
			return False
		self.handle.set_pan(float(value) / 100)

	@property
	def playing(self):
		if self.handle is None:
			return False
		try:
			s = self.handle.is_playing
		except Exception:
			return False
		return s

	def close(self):
		if self.handle:
			self.handle.free()
def play3D(sample, x=0, y=0, z=0, lx=0, ly=0, lz=0, vol=100, pitch=100, pan=0, vol_step=1, pitch_step=1, pan_step=1):
    s = sound()
    s.stream(sample)
    s.volume = vol
    s.pitch = pitch
    s.pan = pan
    
    # Tính toán hiệu ứng 3D
    dx = lx - x
    dy = ly - y
    dz = lz - z
    distanceVolume = math.sqrt(dy * dy + dz * dz)
    s.volume = max(0, min(100, vol - (distanceVolume * vol_step)))    
    distancePitch = math.sqrt(dy * dy + dz * dz)
    s.pitch = max(0, min(100, pitch - (distancePitch * pitch_step)))    
    distancePan = math.sqrt(dx * dx)
    s.pan = max(0, min(100, pan - (distancePan * pan_step)))    
    s.play()
def playOneShot(sample, vol=100, pitch=100):
	s = sound()
	s.sample(sample)
	s.volume = vol
	s.pitch = pitch
	s.play()

def playsound(sample, stream=True, vol=100, pitch=100, pan=0, stop=False, play_looped=False, play_wait=False,fadetime=None):
	s = sound()
	if stream:
		s.load(sample)
	else:
		s.sample(sample)
	s.play()
	if stop:
		s.stop()
	if play_looped:
		s.play_looped()
	if play_wait:
		s.play_wait()
	s.volume = vol
	s.pitch = pitch
	s.pan = pan
	if fadetime:
		s.fadeout(fadetime)
	return s

def loadSounds(globalSelf, paths,checkProgress=False, doneRead=False, readTimeLoading=False):
	sounds = {}
	all_files = glob.glob(paths)
	total_files = len(all_files)
	start_time = time.time()  # Bắt đầu đo thời gian

	if total_files == 0:
		globalSelf.say("No sound files found.")
		return sounds

	with concurrent.futures.ThreadPoolExecutor() as executor:
		future_to_file = {executor.submit(loadSoundFile, file): file for file in all_files}

		for i, future in enumerate(concurrent.futures.as_completed(future_to_file)):
			file = future_to_file[future]
			try:
				filename, sample = future.result()
				sounds[filename] = sample
			except Exception as e:
				globalSelf.say(f"Error loading file '{file}': {e}")

			progress = int((i + 1) / total_files * 100)
			if globalSelf and globalSelf.keyPressed(k.space.value):
				if checkProgress:
					globalSelf.frameUpdate()
					globalSelf.say(_("Progress: %d") % progress)
	end_time = time.time()  # Kết thúc đo thời gian
	if doneRead:
		globalSelf.say("All sound files have been loaded.")
	load_duration = end_time - start_time
	load_duration_int = int(load_duration)
	if readTimeLoading:
		globalSelf.say(f"{load_duration_int} seconds")

	return sounds

def loadSoundFile(file):
	return os.path.basename(file), sound_lib.sample.Sample(file)
