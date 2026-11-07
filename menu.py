# -*- coding: utf-8 -*-
# Idea from Yukio Nozawa and continue by ihcyna(Labubu)

from . import key
from .sound_pool import *
from .timer import *
import re

CONFIG = {"permissions": ["read", "move", "enter", "cancel", "hotkey"],
          "hotkey-text": "%s", "np-text": "%d of %d", "readNP": False,
          "sep-text": ", ", "disabled-text": "unavailable",
          "cursor-sound": None, "enter-sound": None, "cancel-sound": None, "open-sound": None}


class menu:
	"""A simple nonblocking menu class."""
	def __init__(self):
		self.init = self.initialize

	def __del__(self):
		pass

	def initialize(self, wnd, ttl="no title", items=None, cursorSound=None, enterSound=None, cancelSound=None, openSound=None, keyRead=False, readNP=False, config=None):
		self.config = {**CONFIG, **(config or {})}
		self.readNP = readNP or self.config["readNP"]
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
		self.cursorSound = cursorSound or self.config["cursor-sound"]
		self.enterSound = enterSound or self.config["enter-sound"]
		self.cancelSound = cancelSound or self.config["cancel-sound"]
		self.openSound = openSound or self.config["open-sound"]
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

	def allowed(self, name):
		return -1 in self.config["permissions"] or name in self.config["permissions"]

	def parseShortcut(self, elem):
		"""Accept &x, &{ctrl+x}, a tab suffix, or a label/hotkey dict."""
		meta = elem.copy() if isinstance(elem, dict) else {}
		text = str(meta.get("label", elem))
		text, sep, suffix = text.partition("\t")
		shortcut = meta.get("hotkey", suffix if sep else None)
		text = text.replace("&&", "\x00")
		pattern = re.escape(self.find_key) + r"(?:\{([^}]+)\}|(.))"
		match = re.search(pattern, text)
		if match:
			shortcut = shortcut or match.group(1) or match.group(2)
			text = text[:match.start()] + (match.group(2) or "") + text[match.end():]
		text = text.replace("\x00", "&")
		if not self.use_shortcut: shortcut = None
		if not shortcut and self.use_shortcut and self.auto_hotkey:
			shortcut = next((char for char in text.lower() if char.isascii() and char.isalnum()), None)
		code = None
		if shortcut:
			try: code = key.chord(shortcut)[0]
			except Exception: code = None
		return text, shortcut.lower() if shortcut else None, code, meta

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
		if self.allowed("read"): self.wnd.say(say_str)
		if self.openSound: playsingle(self.openSound)

	def jumpCursor(self, c, wrap=None):
		"""Jumps to a specific cursor position, handling sounds, edge hits, and wrap-arounds."""
		if not self.items or not self.allowed("move"): return
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
		if self.allowed("read"): self.wnd.say(self.getReadStr())

	def moveTo(self, c):
		"""Alias for jumpCursor to maintain backward compatibility."""
		if self.lastHold < 2: self.lastHold += 1
		self.jumpCursor(c)

	def frameUpdate(self):
		"""The frame updating function for this menu. Call your window's frameUpdate prior to this."""
		if not self.items: return None
		
		up = self.wnd.keyPressing(self.up_key) or (hasattr(self.wnd, "keySliding") and (self.wnd.keySliding("up") or self.wnd.keySlide("up")))
		dn = self.wnd.keyPressing(self.down_key) or (hasattr(self.wnd, "keySliding") and (self.wnd.keySliding("down") or self.wnd.keySlide("down")))
		
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

		if (self.wnd.keyPressed("esc") or (hasattr(self.wnd, "keySlide") and self.wnd.keySlide("left"))) and self.allowed("cancel"):
			self.cancel()
			return -1
			
		if (self.wnd.keyPressed("enter") or (hasattr(self.wnd, "tap") and self.wnd.tap())) and self.allowed("enter") and self.items[self.cursor][3].get("enabled", True):
			self.enter()
			return self.cursor

		# Test declared chords once; aliases cannot consume unrelated keys.
		if self.use_shortcut and self.allowed("hotkey"):
			for shortcut in dict.fromkeys(item[1] for item in self.items if item[1]):
				if self.wnd.keyPressed(shortcut) and key.match(getattr(self.wnd, "mods", key.chord(shortcut)[1]), key.chord(shortcut)[1]):
					return self.processShortcut(key.chord(shortcut)[0], shortcut)

		return None

	def processShortcut(self, code, shortcut=None):
		"""Search for shortcut matches dynamically in self.items (avoids maintaining a 2nd list)."""
		matched_indices = [i for i, item in enumerate(self.items) if item[2] == code and (shortcut is None or item[1] == shortcut) and item[3].get("enabled", True)]
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

	def getString(self, index=None, hotkey=False):
		index = self.cursor if index is None else index
		if 0 <= index < len(self.items): return self.items[index][1 if hotkey else 0] or ""
		return ""

	def getReadStr(self):
		if not self.items or not self.allowed("read"): return ""
		parts = [self.getString()]
		if self.keyRead and self.getString(hotkey=True):
			parts.append(self.config["hotkey-text"] % self.getString(hotkey=True))
		if not self.items[self.cursor][3].get("enabled", True): parts.append(self.config["disabled-text"])
		if self.items[self.cursor][3].get("hint"): parts.append(self.items[self.cursor][3]["hint"])
		if self.readNP: parts.append(self.config["np-text"] % (self.cursor + 1, len(self.items)))
		return self.config["sep-text"].join(parts)

	def hotkey(self, line):
		return line[0].upper() if line else ""

	def Len(self):
		return len(self.items)

	def exit(self):
		return self.wnd.keyPressed("exit")

	def isLast(self, index):
		return index == len(self.items) - 1

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