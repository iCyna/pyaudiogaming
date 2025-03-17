# -*- coding: utf-8 -*-
from copy import copy
import pygame
from enum import Enum, auto
from pygame.locals import *
import os
pygame.init()
class k(Enum):
	s = K_s
	a = K_a
	d = K_d
	f = K_f
	g = K_g
	h = K_h
	j = K_j
	k = K_k
	l = K_l
	q = K_q
	w = K_w
	e = K_e
	r = K_r
	t = K_t
	y = K_y
	u = K_u
	i = K_i
	o = K_o
	p = K_p
	z = K_z
	x = K_x
	c = K_c
	v = K_v
	b = K_b
	n = K_n
	m = K_m
	left = K_LEFT
	right = K_RIGHT
	up = K_UP
	down = K_DOWN
	home = K_HOME
	end = K_END
	page_up = K_PAGEUP
	page_down = K_PAGEDOWN
	enter = K_RETURN
	f1 = K_F1
	f2 = pygame.K_F2
	f3 = K_F3
	f4 = K_F4
	f5 = K_F5
	f6 = K_F6
	f7 = K_F7
	f8 = K_F8
	f9 = K_F9
	f10 = K_F10
	f11 = K_F11
	f12 = K_F12
	fspace = K_BACKSPACE
	jlit = K_DELETE
	lshift = K_LSHIFT
	rshift = K_RSHIFT
	lalt = K_LALT
	ralt = K_RALT
	lcontrol = K_LCTRL
	rcontrol = K_RCTRL
	space = K_SPACE
	tab = K_TAB
	exit = K_ESCAPE
	print_screen = K_PRINT
	sys_req = K_SYSREQ
	insert = K_INSERT
	menu = K_MENU
	capslock = K_CAPSLOCK
	left_bkt = K_LEFTBRACKET  # Phím [
	right_bkt = K_RIGHTBRACKET # Phím ]

	def eq(self, other):
		return self.value == other
	@property
	def to_pygame_int(self):
		"""
		Chuyển đổi giá trị của lớp k sang số nguyên của Pygame.
		"""
		return self.value
	def __eq__(self, other):
		"""
		Override operator '==' để tự động chuyển đổi các giá trị từ lớp k sang số nguyên của Pygame.
		"""
		if isinstance(other, int):
			return self.to_pygame_int == other
		return super().__eq__(other)
def kb(*args):
	keys = pygame.key.get_pressed()
	return all(keys[key.value] for key in args)

def kbs(*key, pressing=False):
	if pressing:
		return pygame.key.get_pressed()[key[0].value]
	else:
		for event in pygame.event.get():
			if event.type == KEYDOWN and pygame.key.get_pressed()[key[0].value]:
				return False