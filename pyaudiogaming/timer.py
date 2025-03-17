import pygame
class Timer:
	"""A simple timer class like bgt."""
	def __init__(self):
		self.restart()

	def restart(self):
		"""Restarts this timer."""
		self.startTick=pygame.time.get_ticks()

	@property
	def elapsed(self):
		"""
		Returns the elapsed time in milliseconds.

		:rtype: int
		"""
		return pygame.time.get_ticks()-self.startTick
#end class Timer
