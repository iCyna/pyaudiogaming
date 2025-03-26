# how to create a window now
# note:
# You need to create a global variable to follow Window because of the functions such as time, key press, etc.
import sys
import v # global variable
from pyaudiogaming.window import *
from pyaudiogaming.menu import *
from pyaudiogaming.key import *
w=Window()
v.main=w
w.initialize(400,300,"examples for a window game")
initializes a menu
m = menu.initialize("main menu please select an option")
m.append("start")
m.append("exit")
# call m.open() to Display menu and etc
m.open()
while True:
	# call frame update to update screen
	w.frameUpdate()
	s = m.frameUpdate()
	if s is not None and s >= 0:
		#We handle it by when users choose any option and Enter it will return the order number or simply speak as this ID ID will activate an event.
		if s == 0: if user return 0 when they in index 0 (line 0 on menu)
			w.say("starting game please wait")
		if s == 1: # when user return on line 1 menu menu 
			w.say("exiting please wait a sec")
			sys.exit()
	# You can also do the following
	if s == -1: sys.exit() #
	# When the user presses Escape will return ID -1
	# ok next for press key
	if w.keyPressed(k.a.value): w.say("you pressed a")
	if w.keyPressing(k.s.value, t=200): w.say("pressing key s loop")
	# The difference between keypreded and keypressing is that Keypreded can only press once and cannot repeat the key while the keypressing is the opposite they can repeat the key if you press and hold the parameter T is the time for the speed to repeat between the times (in the Mily second)
	if w.keyPressed(k.m.value): w.message("this is message", p=None)
	# The first parameter for Message will be displayed P is the parameter when the Message menu is displayed and will sound