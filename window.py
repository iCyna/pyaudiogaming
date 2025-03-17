# -*- coding: utf-8 -*-
#Basic window, timer, speech, menu handling...
import pygame, wx, sys, time, inputBox
from .accessible_output2.outputs.auto import *
from copy import copy
from pygame.locals import *
from .key import *
from .timer import *
from enum import Enum, auto

class Window():

	"""Just a pygame window wrapper. As the name implies, you mustn't create multiple singletonWindow's in your game. You should inherit this class and make your own app main class to make your code easy to read."""
	def __init__(self):
		self.wxInstance=wx.App()
		pygame.init()
		self.clock=pygame.time.Clock()
		self.speech_history = []
		self.history_index = -1  # Index to navigate speech history
		self.tmr = Timer()

	def __del__(self):
		#pygame.quit()
		pass

	def initialize(self,x,y,ttl):
		"""
		Initializes the game window. Returns True on success or False for failure.

		:rtype: bool
		"""
		self.screen = pygame.display.set_mode((x, y))
		pygame.display.set_caption(ttl)
		self.keys=[0]*255
		self.previousKeys=[0]*255
		self.speech=Auto()
		return True

	def frameUpdate(self):
		"""
A function that must be called once per frame. Calling this function will keep the 60fps speed.

When user presses alt+f4 or the x icon, this function attempts to shut down the game by calling self.exit method. It is possible that the exit message is canceled by the onExit callback currently set.
"""
		self.clock.tick(60)
		self.screen.fill((255,63,10,))
		pygame.display.update()
		self.previousKeys=copy(self.keys)
		self.keys=pygame.key.get_pressed()
		if self.keyPressed(k.lcontrol.value) or self.keyPressed(k.rcontrol.value): self.speech.silence()
		for event in pygame.event.get():
			if event.type == QUIT: self.exit()
		try:
			if self.keyPressed(k.left_bkt.value):  # Previous history item
				if self.history_index > 0:
					self.history_index -= 1
					self.saync(self.speech_history[self.history_index])
			if self.keyPressed(k.right_bkt.value):  # Next history item
				if self.history_index < len(self.speech_history) - 1:
					self.history_index += 1
					self.saync(self.speech_history[self.history_index])
			if (self.keyPressing(k.lshift.value) or self.keyPressing(k.rshift.value)) and self.keyPressed(k.left_bkt.value):
				self.history_index = 0
				self.saync(self.speech_history[self.history_index])
			if (self.keyPressing(k.lshift.value) or self.keyPressing(k.rshift.value)) and self.keyPressed(k.right_bkt.value):
				self.history_index = len(self.speech_history)
				self.saync(self.speech_history[self.history_index])
		except IndexError:pass

		#end event
	#end frameUpdate

	def keyPressed(self,key):
		"""
		Retrieves if the specified key has changed to "pressed" from "not pressed" at the last frame. Doesn't cause key repeats.

		:rtype: bool
"""
		return self.keys[key] and not self.previousKeys[key]

	def keyPressing(self,key, t=0):
		"""
		Retrieves if the specified key is being pressed. Key repeats at 60rp/sec.

		:rtype: bool
"""
		if not self.keys[key]:
			return self.keys[key] and not self.previousKeys[key]
		elif self.keys[key]:
			if self.tmr.elapsed >= t:
				self.tmr.restart()
				return self.keys[key]

	def wait(self,msec):
		"""waits for a specified period of milliseconds while keeping the window looping. """
		t=Timer()
		while t.elapsed<msec:
			self.frameUpdate()
		#end loop
	#end wait

	def say(self,str, i=True):
		"""tts speech"""
		self.speech.speak(str, interrupt=i)
		self.speech_history.append(str)
		self.history_index=len(self.speech_history)

	def saync(self,str):
		"""tts speech"""
		speech_history = self.speech.speak(str, interrupt=True)

	def get_volume(self):
		return self.speech.get_volume()

	def set_volume(self, value):
		return self.speech.set_volume(value)

	def get_pitch(self):
		return self.speech.get_pitch()

	def set_pitch(self, value):
		return self.speech.set_pitch(value)

	def get_rate(self):
		return self.speech.get_rate()

	def set_rate(self, value):
		return self.speech.set_volume(value)

	def get_voice(self):
		return self.speech.get_voice()

	def set_voice(self, type):
		return self.speech.set_voice()

	def exit(self):
		"""Attempt to exit the game. It is canceled if the onExit callback is set and it returned False."""
		if not self.onExit(): return
		sys.exit()

	def onExit(self):
		"""
		Override this method to define your own onExit code. It is automatically called from self.frameUpdate method when the game is being closed.

		You should return True when game can exit normally or False if you want to cancel the exit event.

		:rtype: bool
		"""
		return True#This is default

	def input(self,title,message, password=False, dir=False, file=False):
		"""Shows a text input dialog and returns what was input by the user. Returns None when canceled."""
		ret=inputBox.kbt(None, title, password, password=password, dir_dialog=dir, file_dialog=file)
		return ret

	def message(self, m, open=None):
		self.say(m)
		while True:
			self.frameUpdate()
			if self.keyPressed(k.left.value) or self.keyPressed(k.right.value) or self.keyPressed(k.up.value) or self.keyPressed(k.down.value): self.say(m)
			if self.keyPressed(k.enter.value):
				if open is not None:
					bgtsound.playOneShot(p)
				break

	def messageGui(self, title, message, type=inputBox.INFO):
		i=inputBox.dialogMessage(title, message, type)
		return i
	#end input
#end class singletonWindow
