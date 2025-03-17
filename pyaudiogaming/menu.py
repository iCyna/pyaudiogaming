import pygame
from .keyrstr import *
from .key import *
from .bgsounds import *
from .timer import *

class menu:
	"""A simple nonblocking menu class."""
	def __init__(self):
		pass
	def __del__(self):
		pass
	def initialize(self,wnd,ttl="no title", items=None, cursorSound=None, enterSound=None, cancelSound=None, openSound=None, keyRead=True):
		"""
		Initializes the menu with window instance, title and initial menu items. Requires a singletonWindow instance for this menu to work. Menu items should be a sequence of strings (not an array). the "#" character is used as the menu delimitor. 

		:param wnd: Window to which this menu is bound.
		:type wnd: SingletonWindow
		:param ttl: Menu title.
		:type ttl: str
		:param items: Default items.
		:type items: list
		:param CursorSound: Sample instance played when user cycles through the menu items.
		:type enterSound: sound_lib.sample
		:param enterSound: Sample instance played when user presses enter on a menu item.
		:type enterSound: sound_lib.sample
		:param cancelSound: Sample instance played when user cancels the menu.
		:type enterSound: sound_lib.sample
		"""
		self.wnd=wnd
		self.title=ttl
		self.items=[]
		self.shortcuts=[]
		if items: self.append(items)
		self.cursor=0
		self.cursorSound=cursorSound
		self.enterSound=enterSound
		self.cancelSound=cancelSound
		self.openSound = openSound
		self.keyRead=keyRead
		self.holdTimer=Timer()
		self.lastHold=0
		self.code={"exit": -1}
		self.up_key=k.up.value
		self.down_key=k.down.value
		self.lshift=None
		self.rshift=None

	def append(self,lst, shortcut=True):
		"""Adds one or multiple menu items. By setting shortcut false, you can skip parsing for shortcut key registration."""
		if isinstance(lst,str):
			self.items.append(self.append_internal(lst,shortcut))
			return
		#end single append
		for elem in lst:
			self.items.append(self.append_internal(elem,shortcut))

	def insert(self,index,item):
		"""Inserts an item at the specified position.

		:param index: Index to add.
		:type index: int
		:item: Item to add.
		:type item: str
		"""
		self.items.insert(index,self.append_internal(item))

	def append_internal(self,elem,processShortcut=True):
		"""Parses and makes a single item tuple. Called from append.

		:param elem: Element to add.
		"""
		if not processShortcut: return (elem, None, None)
		shortcut, shortcut_str=self.parseShortcut(elem)
		if shortcut:
			elem=elem[0:len(elem)-2]
			self.shortcuts.append((shortcut,len(self.items)))
		#end if shortcut registration
		return (elem,shortcut_str,shortcut)

	def parseShortcut(self,elem):
		"""Parses the menu item string and returns shortcut keycode and string if detected. Otherwise, set both as None.
		:param elem: Element to parse.
		"""
		shortcut=None
		shortcut_str=None
		l=len(elem)
		if l<=3: return None, None
		last=elem[l-2:l].upper()
		if last[0]=="&":
			try:
				cmd=STR_TO_KEY[last[1]]
			except KeyError:
				pass
			else:
				shortcut=cmd
				shortcut_str=last[1]
			#end else
		#end if shortcut input exists
		return shortcut, shortcut_str

	def remove(self,index):
		"""Deletes the item at the specified index.

		:param index: index to delete.
		:type index: int
		"""
		for elem in self.shortcuts[:]:
			if elem[1] == index: self.shortcuts.remove(elem)
		self.items.pop(index)

	def modify(self,index,new):
		"""Modifies the existing menu item.

		:param index: Index to modify.
		:type index: int
		:param new: New menu item
		:type new: str
		"""
		self.remove(index)
		self.insert(index,new)

	def open(self):
		"""Starts the menu. You should call frameUpdate() to keep the menu operate after this. """
		if len(self.items)==0: return
		self.wnd.say("%s, %s" % (self.title, self.getReadStr()))
		if self.openSound is not None: playOneShot(self.openSound)

	def frameUpdate(self):
		"""The frame updating function for this menu. You should call your window's frameUpdate prior to call this function. Returns None for no action, -1 for cancellation and 0-based index for being selected. """
		up=self.wnd.keyPressing(self.up_key)
		dn=self.wnd.keyPressing(self.down_key)
		lalt = self.wnd.keyPressing(K_LALT)
		use_shift = (self.lshift is not None and self.wnd.keyPressing(self.lshift)) or (self.rshift is not None and self.wnd.keyPressing(self.rshift))
		processArrows=False
		if not up and not dn: self.lastHold=0
		if self.lastHold==0: processArrows=True
		if self.lastHold==1 and self.holdTimer.elapsed>=600:
			processArrows=True
		#end 600 ms hold
		if self.lastHold==2 and self.holdTimer.elapsed>=50:
			processArrows=True
		#end 50 ms hold
		if processArrows:
			if not self.lshift and up:
				self.moveTo(self.cursor-1)
			elif self.lshift and self.wnd.keyPressing(self.lshift) and up:
				self.moveTo(self.cursor-1)
			elif dn:
				self.moveTo(self.cursor+1)

		#end arrow keys
			if self.wnd.keyPressed(K_HOME) and self.cursor!=0: self.moveTo(0)
			if self.wnd.keyPressed(K_END) and self.cursor!=len(self.items): self.moveTo(len(self.items)-1)
		if self.wnd.keyPressed(K_PAGEUP):
			n=int(len(self.items)/20)
			if n>0: self.moveTo(self.cursor-n)
		#end pageup
		if self.wnd.keyPressed(K_PAGEDOWN):
			n=int(len(self.items)/20)
			if n>0: self.moveTo(self.cursor+n)
		#end pagedown
		if self.wnd.keyPressed(K_SPACE): self.moveTo(self.cursor)
		if self.wnd.keyPressed(K_F12) or self.wnd.keyPressing(K_LCTRL) and self.wnd.keyPressed(K_c): copy.copy(getString(getCursorPos()))
		if self.wnd.keyPressed(K_ESCAPE):
			self.cancel()
			return -1
		#end cancel
		if self.wnd.keyPressed(K_RETURN):
			self.enter()
			return self.cursor
		#end enter
		if len(self.shortcuts)>0:
			for command in STR_TO_KEY.values():
				if self.wnd.keyPressed(command): return self.processShortcut(command)
			#end shortcut
		#end at least one shortcut is active
		return None
	#end frameUpdate

	def processShortcut(self,code):
		"""Search for the shortcut actions that is associated with the given command. Returns the index if one item is matched and instantly selected, otherwise None. This method may move focus or trigger the enter event as the result of searching.

		:param code: key code.
		:type code: int
		"""
		matched=[]
		for elem in self.shortcuts:
			if elem[0]==code: matched.append(elem)
		#end for
		if len(matched)==0: return
		if len(matched)==1:
			self.cursor=matched[0][1]
			self.enter()
			return self.cursor
		#end instant selection
		i=self.cursor
		found=False
		while i<len(self.items)-1:
			i+=1
			if self.items[i][2]==code:
				found=True
				break
			#end if
		#end while
		if found:
			self.moveTo(i)
			return None
		#end if found at the lower column
		#Research from the top
		i=-1
		while i<len(self.items)-1:
			i+=1
			if self.items[i][2]==code:
				found=True
				break
		if found:
			self.moveTo(i)
			return None
		#end research
	#end processShortcut

	def cancel(self):
		"""Internal function which is triggered when canceling the menu. """
		if self.cancelSound is not None: playOneShot(self.cancelSound)

	def enter(self):
		"""Internal function which is triggered when selecting an option. """
		if self.enterSound is not None and self.cursor >0: playOneShot(self.enterSound)

	def getCursorPos(self):
		"""Returns the current cursor position. """
		return self.cursor

	def getString(self,index):
		"""Retrieves the menu item string at the specified index. Returns empty string when out of bounds.

		:param index: Index.
		:rtype: str
		"""
		if index<0 or index>=len(self.items): return ""
		return self.items[index][0]

	def moveTo(self,c):
		"""Moves the menu cursor to the specified position and reads out the cursor. It also sets the lastHold status, which triggers key repeats. I decided not to use pygame key repeat functions. """
		if self.lastHold<2: self.lastHold+=1
		if c<0 or c>len(self.items)-1: return
		self.holdTimer.restart()
		if self.cursorSound is not None: playOneShot(self.cursorSound)
		self.cursor=c
		self.wnd.say(self.getReadStr())
	#end moveTo

	def getReadStr(self):
		"""Returns a string which should be used as readout string for the current cursor.

:rtype: str
"""
		s=self.items[self.cursor][0]
		if self.keyRead:
			if self.items[self.cursor][1] is not None: s+=", "+self.items[self.cursor][1]
		return s

	def getTitle(self):
		if self.title is not None: return self.title

	def setTitle(self, newTitle):
		self.title = newTitle

	def getOpenSound(self):
		if self.openSound is not None: return self.openSound

	def setOpenSound(self, newSoundOpen):
		self.openSound = newSoundOpen

	def getCancelSound(self):
		return self.cancelSound

	def setCancelSound(self, newCancelSound):
		self.cancelSound=newCancelSound
		return newCancelSound

	def getEnterSound(self, newEnterSound):
		return self.enterSound

	def setEnterSound(self, newEnterSound):
		self.enterSound = newEnterSound
		return newEnterSound

	def hotkey(self, line):
		#retrieves the first character and you can use it to make suitable shortcut characters for lists or auto-added documents
		hotkey = line[0].upper()
		return hotkey

	def Len(self):
		#Returns the length of items and displays it as an int
		return int(len(self.items))
	def exit(self):
		return wld.keyPressed(k.exit.value)
	def isLast(self,index):
		"""Retrieves if the given index is the last item of the menu. This is particularly useful when you want to bind the last action to exit or close.

		:param index: index.
		:type index: int
		:rtype: bool
		"""
		return self.cursor==len(self.items)-1

#end class menu