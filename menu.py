# -*- coding: utf-8 -*-
# Idea from Yukio Nozawa and continue by ihcyna(Labubu)

from . import key
from .sound_pool import *
from .timer import *

class menu:
	"""A simple nonblocking menu class."""
	def __init__(self):
		self.init = self.initialize

	def __del__(self):
		pass

	def initialize(self, wnd, ttl="no title", items=None, cursorSound=None, enterSound=None, cancelSound=None, openSound=None, keyRead=False):
		self.wnd = wnd
		self.title = ttl
		self.items = [] # Stores tuple: (display_text, shortcut_str, shortcut_key)
		self.find_key = "&"
		self.auto_hotkey = True
		self.auto_enter_fMatched = False
		self.use_shortcut = True
		self.match_cursor = True # True to wrap around edges
		
		# Cursor & Navigation
		self.cursor = 0
		self.keyRead = keyRead
		self.holdTimer = Timer()
		self.lastHold = 0
		self.up_key = "up"
		self.down_key = "down"
		self.lshift = None
		self.rshift = None
		
		# Sounds
		self.cursorSound = cursorSound
		self.enterSound = enterSound
		self.cancelSound = cancelSound
		self.openSound = openSound
		self.edgeSound = None
		self.betweenSound = None # Played when wrapping around (end to start / start to end)
		self.removeSound = None
		self.modifySound = None
		self.insertSound = None
		self.previousCursorSound = None
		self.nextCursorSound = None

		if items:
			if isinstance(items, str): self.append(items)
			elif isinstance(items, list):
				for i in items: self.append(i)

	def parseShortcut(self, elem):
		"""Parses shortcut using the find_key. Returns (display_name, shortcut_str, shortcut_keycode)"""
		if not self.use_shortcut or not isinstance(elem, str):
			return (elem, None, None)
		
		idx = elem.find(self.find_key)
		if idx != -1 and idx + 1 < len(elem):
			shortcut_str = elem[idx + 1].lower()
			display_elem = elem[:idx] + elem[idx + 1:]
			shortcut_key = None
			try:
				# Assumes key.ksum holds the string-to-keycode mapping
				shortcut_key = key.ksum.get(shortcut_str)
			except AttributeError:
				pass
			return (display_elem, shortcut_str, shortcut_key)
		return (elem, None, None)

	def append(self, elem):
		"""Adds a menu item."""
		self.items.append(self.parseShortcut(elem))

	def insert(self, index, elem):
		"""Inserts an item at the specified position."""
		self.items.insert(index, self.parseShortcut(elem))
		if self.insertSound: playsingle(self.insertSound)

	def remove(self, index):
		"""Deletes the item at the specified index."""
		if 0 <= index < len(self.items):
			self.items.pop(index)
			if index <= self.cursor and self.cursor > 0:
				self.cursor -= 1
			if self.removeSound: playsingle(self.removeSound)

	def modify(self, index, new_elem):
		"""Modifies an existing menu item."""
		if 0 <= index < len(self.items):
			self.items[index] = self.parseShortcut(new_elem)
			if self.modifySound: playsingle(self.modifySound)

	def open(self):
		"""Starts the menu."""
		if not self.items: return
		say_str = f"{self.title}, {self.getReadStr()}" if self.title else self.getReadStr()
		self.wnd.say(say_str)
		if self.openSound: playsingle(self.openSound)

	def jumpCursor(self, c, wrap=None):
		"""Jumps to a specific cursor position, handling sounds, edge hits, and wrap-arounds."""
		if not self.items: return
		wrap = self.match_cursor if wrap is None else wrap
		old_c = self.cursor
		max_idx = len(self.items) - 1
		is_wrap = False

		if c < 0:
			c = max_idx if wrap else 0
			is_wrap = wrap and max_idx > 0
		elif c > max_idx:
			c = 0 if wrap else max_idx
			is_wrap = wrap and max_idx > 0

		self.cursor = c
		self.holdTimer.restart()

		# Determine the correct sound to play
		sound = None
		if is_wrap:
			sound = self.betweenSound or self.edgeSound or self.cursorSound
		elif (c == 0 and old_c == 0) or (c == max_idx and old_c == max_idx):
			sound = self.edgeSound or self.cursorSound
		elif c < old_c:
			sound = self.previousCursorSound or self.cursorSound
		elif c > old_c:
			sound = self.nextCursorSound or self.cursorSound
		else:
			sound = self.cursorSound # Default fallback

		if sound: playsingle(sound)
		self.wnd.say(self.getReadStr())

	def moveTo(self, c):
		"""Alias for jumpCursor to maintain backward compatibility."""
		if self.lastHold < 2: self.lastHold += 1
		self.jumpCursor(c)

	def frameUpdate(self):
		"""The frame updating function for this menu. Call your window's frameUpdate prior to this."""
		if not self.items: return None
		
		up = self.wnd.keyPressing(self.up_key)
		dn = self.wnd.keyPressing(self.down_key)
		
		processArrows = False
		if not up and not dn: 
			self.lastHold = 0
		if self.lastHold == 0: 
			processArrows = True
		elif self.lastHold == 1 and self.holdTimer.elapsed >= 600:
			processArrows = True
		elif self.lastHold == 2 and self.holdTimer.elapsed >= 50:
			processArrows = True

		# Process Navigation
		if processArrows:
			if up: self.moveTo(self.cursor - 1)
			elif dn: self.moveTo(self.cursor + 1)

		if self.wnd.keyPressed("home") and self.cursor != 0: 
			self.jumpCursor(0, wrap=False)
		if self.wnd.keyPressed("end") and self.cursor != len(self.items) - 1: 
			self.jumpCursor(len(self.items) - 1, wrap=False)
			
		page_step = max(1, int(len(self.items) / 20))
		if self.wnd.keyPressed("page_up"): self.moveTo(self.cursor - page_step)
		if self.wnd.keyPressed("page_down"): self.moveTo(self.cursor + page_step)

		if self.wnd.keyPressed("esc"):
			self.cancel()
			return -1
			
		if self.wnd.keyPressed("enter"):
			self.enter()
			return self.cursor

		# Shortcut Processing
		if self.use_shortcut:
			for command in getattr(key, 'ksum', {}):
				if self.wnd.keyPressed(command.lower()):
					return self.processShortcut(key.ksum[command])
					
		return None

	def processShortcut(self, code):
		"""Search for shortcut matches dynamically in self.items (avoids maintaining a 2nd list)."""
		matched_indices = [i for i, item in enumerate(self.items) if item[2] == code]
		if not matched_indices: return None

		if len(matched_indices) == 1:
			self.jumpCursor(matched_indices[0])
			if self.auto_enter_fMatched: self.enter()
			return self.cursor

		# Cycle through matched shortcuts downward
		for idx in matched_indices:
			if idx > self.cursor:
				self.jumpCursor(idx)
				return None
				
		# If at the end, cycle back to the first matched item
		self.jumpCursor(matched_indices[0])
		return None

	def cancel(self):
		if self.cancelSound: playsingle(self.cancelSound)

	def enter(self):
		if self.enterSound and self.cursor >= 0: playsingle(self.enterSound)

	def getCursorPos(self):
		return self.cursor

	def getString(self, index):
		if 0 <= index < len(self.items):
			return self.items[index][0]
		return ""

	def getReadStr(self):
		if not self.items: return ""
		s = self.items[self.cursor][0]
		shortcut = self.items[self.cursor][1]
		if self.keyRead and shortcut: 
			s += f", {shortcut}"
		return s

	def hotkey(self, line):
		return line[0].upper() if line else ""

	def Len(self):
		return len(self.items)

	def exit(self):
		return self.wnd.keyPressed("exit")

	def isLast(self, index):
		return self.cursor == len(self.items) - 1

	# Getters & Setters
	def getTitle(self): return self.title
	def setTitle(self, newTitle): self.title = newTitle
	
	def getOpenSound(self): return self.openSound
	def setOpenSound(self, newSound): self.openSound = newSound
	
	def getCancelSound(self): return self.cancelSound
	def setCancelSound(self, newSound): self.cancelSound = newSound
	
	def getEnterSound(self): return self.enterSound
	def setEnterSound(self, newSound): self.enterSound = newSound

# end class menu