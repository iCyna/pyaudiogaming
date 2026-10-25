# -*- coding: utf-8 -*-
#virtual box multifunctional
# copyright 2025 belong ihcyna (Labubu)<phucnggo29@gmail.com>.

import pygame
from .sound_pool import playsingle
from .utils import get_window
from .buffer import frame as bf
INPUT_CONFIG={
	"callback-default": None,
	"read char": True,
	"read word": True,
	"permissions": [
		-1, # Allows everything
		0, # can write
		1, # can delete
		2, # can read
		3, # can capital letters
		4, # can non-latin
		5, # can space
		6, # can new line
		7, # can symbols
		8, # can letters
		9, # can numbers
		10, # can undo
		11, # can redo
		12, 13, 14, # cut (needs 1, 12, 13), copy, paste
	],
	"blank-sound": None,
	"write-sound": None,
	"capital write-sound": None,
	"delete-sound": None,
	"space-sound": None,
	"new line-sound": None,
	"open-sound": None,
	"confirm-sound": None,
	"exit-sound": None,
	"edge text-sound": None,
	"move text-sound": None,
	"move line-sound": None,
	"undo-sound": None,
	"redo-sound": None,
	"cut-sound": None,
	"copy-sound": None,
	"paste-sound": None,
	"cannot write-sound": None,
	"cannot capital write-sound": None,
	"cannot read-sound": None,
	"cannot delete-sound": None,
	"cannot undo-sound": None,
	"cannot redo-sound": None,
	"cannot cut-sound": None,
	"cannot copy-sound": None,
	"cannot paste-sound": None,
	"blank-text": "blank",
	"space-text": "%s space",
	"new line-text": "line feed",
	"capital-text": "CAPITAL %s",
	"delete-text": "%s deleting",
	"unselected-text": "Unselected",
	"select all-text": "%s selected",
	"select max-text": "%d characters",
	"select max all-text": "all",
	"select max all": -1,
	"select all-sound": None,
	"cannot write-text": "",
	"cannot capital write-text": "",
	"cannot read-text": "star",
	"cannot delete-text": "",
	"cannot undo-text": "",
	"cannot redo-text": "",
	"cannot cut-text": "No cutting allowed here",
	"cannot copy-text": "No copying allowed here",
	"cannot paste-text": "No pasting allowed here",
}

def message(m, callback=None, open=None, move=None, close=None, window=None):
	if not window: window=get_window()
	window.say(m)
	if open:
		playsingle(open)
	while True:
		window.frameUpdate()
		if callback: callback()
		if window.keyPressed("left") or window.keyPressed("right") or window.keyPressed("up") or window.keyPressed("down"):
			if move: playsingle(move)
			window.say(m)
		if window.keyPressed("enter") or window.keyPressed("exit"):
			if close: playsingle(close)
			break

def get_conput(name, key, fallback=None):
	try:
		return INPUT_CONFIG.get(f"{key}-{name}", fallback) if key != "" else {k: v for k,v in INPUT_CONFIG.items() if f"-{name}" in k}
	except: return fallback

def set_conput(data, fallback={}):
	global INPUT_CONFIG
	try:
		for a, b in data.items():
			INPUT_CONFIG[a]=b
		return INPUT_CONFIG
	except: return fallback

def input(title="", text="", callback=None, password=False, get_data=True, new_config={}):
	from .buffer import frame as bf
	config = INPUT_CONFIG.copy()
	if new_config:
		config.update(new_config)

	if callback is None:
		callback = config.get("callback-default")

	if password:
		per = [-1, 2, 4, 5, 6, 12, 13, 14]
		config["permissions"] = [i for i in config["permissions"] if i not in per]

	pms = config["permissions"]
	def has_perm(p):
		return -1 in pms or p in pms

	def play(snd_key, txt_key=None, *args):
		if config.get(snd_key):
			playsingle(config[snd_key])
		elif txt_key and config.get(txt_key):
			txt = config[txt_key]
			if args:
				try: txt = txt % args
				except TypeError: pass
			if txt != "": bf.say(txt)

	def say_content(txt, is_char=False):
		if txt == "" or txt is None:
			play("blank-sound", "blank-text")
			return
		if not has_perm(2):
			if config.get("cannot read-sound"):
				playsingle(config["cannot read-sound"])
			mask = config.get("cannot read-text", "star")
			bf.say(mask if (is_char or len(txt) == 1) else " ".join([mask] * len(txt)))
			return
		if is_char and len(txt) == 1:
			if txt == " ":
				bf.say(config.get("space-text", "%s space") % "")
			elif txt.isupper():
				bf.say(config.get("capital-text", "CAPITAL %s") % txt)
			else:
				bf.say(txt)
		else:
			bf.say(txt)

	try:
		if not pygame.scrap.get_init():
			pygame.scrap.init()
	except Exception:
		pass
	pygame.key.start_text_input()

	lines = text.split("\n") if text else [""]
	y = len(lines) - 1
	x = len(lines[y])
	startx, endx = -1, -1
	starty, endy = -1, -1
	editing = ""

	undo_stack = []
	redo_stack = []

	def save_state():
		undo_stack.append((lines.copy(), x, y))
		if len(undo_stack) > 100:
			undo_stack.pop(0)
		redo_stack.clear()

	def has_selection():
		return startx != -1 and (startx != endx or starty != endy)

	def clear_selection(announce=False):
		nonlocal startx, endx, starty, endy
		if has_selection() and announce:
			play(None, "unselected-text")
		startx = endx = starty = endy = -1

	def norm_sel():
		if (starty < endy) or (starty == endy and startx <= endx):
			return starty, startx, endy, endx
		return endy, endx, starty, startx

	def get_selected_text():
		if not has_selection(): return ""
		sy, sx, ey, ex = norm_sel()
		if sy == ey:
			return lines[sy][sx:ex]
		res = [lines[sy][sx:]]
		for row in range(sy + 1, ey):
			res.append(lines[row])
		res.append(lines[ey][:ex])
		return "\n".join(res)

	def announce_selection():
		sel_txt = get_selected_text()
		if not sel_txt: return
		if config.get("select all-sound"):
			playsingle(config["select all-sound"])
		max_cfg = config.get("select max all", -1)
		n = len(sel_txt)
		full_txt = "\n".join(lines)
		if max_cfg == 0 or (sel_txt == full_txt and max_cfg == -1 and n <= 500):
			label = config.get("select max all-text", "all") if max_cfg == 0 else (sel_txt if has_perm(2) else config.get("select max-text", "%d characters") % n)
		elif (max_cfg == -1 and n > 500) or (max_cfg > 0 and n >= max_cfg) or not has_perm(2):
			label = config.get("select max-text", "%d characters") % n
		else:
			label = sel_txt
		bf.say(config.get("select all-text", "%s selected") % label)

	def delete_selection():
		nonlocal x, y
		if not has_selection(): return False
		sy, sx, ey, ex = norm_sel()
		deleted = get_selected_text()
		if sy == ey:
			lines[sy] = lines[sy][:sx] + lines[sy][ex:]
		else:
			lines[sy] = lines[sy][:sx] + lines[ey][ex:]
			del lines[sy + 1 : ey + 1]
		y, x = sy, sx
		clear_selection(announce=False)
		return deleted

	def check_perm(char):
		if has_perm(-1): return True, False
		if not has_perm(0): return False, False
		if char == "\n": return has_perm(6), False
		is_space = (char == " ")
		is_num = char.isdigit()
		is_alpha = char.isalpha()
		is_upper = char.isupper()
		is_non_latin = not char.isascii() and is_alpha

		if is_space and not has_perm(5): return False, False
		if is_num and not has_perm(9): return False, False
		if is_alpha:
			if not has_perm(8): return False, False
			if is_upper and not has_perm(3): return False, True
			if is_non_latin and not has_perm(4): return False, False
		if not is_space and not is_num and not is_alpha:
			if not has_perm(7): return False, False
		return True, False

	def insert_text(txt, is_paste=False):
		nonlocal x, y
		valid_chars = []
		for ch in txt:
			if ch == "\r": continue
			ok, cap_denied = check_perm(ch)
			if ok:
				valid_chars.append(ch)
			else:
				if cap_denied:
					play("cannot capital write-sound", "cannot capital write-text")
				else:
					play("cannot write-sound", "cannot write-text")
		valid_str = "".join(valid_chars)
		if not valid_str: return False

		save_state()
		if has_selection():
			delete_selection()

		parts = valid_str.split("\n")
		if len(parts) == 1:
			lines[y] = lines[y][:x] + valid_str + lines[y][x:]
			x += len(valid_str)
		else:
			right_part = lines[y][x:]
			lines[y] = lines[y][:x] + parts[0]
			for idx, p in enumerate(parts[1:], 1):
				lines.insert(y + idx, p)
			y += len(parts) - 1
			x = len(parts[-1])
			lines[y] += right_part

		if not is_paste:
			if valid_str.isupper() and len(valid_str) == 1:
				play("capital write-sound", "capital-text", valid_str if has_perm(2) else config.get("cannot read-text", "star"))
				if config.get("read char"):
					say_content(valid_str, is_char=False)
			elif valid_str == " ":
				if config.get("read word"):
					words = lines[y][:x-1].split()
					if words:
						w = words[-1] if has_perm(2) else config.get("cannot read-text", "star")
						play("space-sound", "space-text", w)
					else:
						play("space-sound", None)
			else:
				play("write-sound", None)
				if config.get("read char"):
					say_content(valid_str, is_char=False)
		return True

	play("open-sound", None)
	if title: bf.say(title)

	while True:
		bf.frameUpdate()
		if callback: callback()

		ctrl = bf.keyPressing("lcontrol") or bf.keyPressing("rcontrol")
		shift = bf.keyPressing("lshift") or bf.keyPressing("rshift")

		# Audio feedback when user physically presses Backspace (mirrors original vb.py behavior)
		if bf.keyPressed("backspace"):
			if not has_perm(1):
				play("cannot delete-sound", "cannot delete-text")
			elif has_selection():
				sel = get_selected_text()
				play("delete-sound", "delete-text", sel if has_perm(2) else config.get("cannot read-text", "star"))
			elif x > 0:
				play("delete-sound", "delete-text", lines[y][x-1] if has_perm(2) else config.get("cannot read-text", "star"))
			elif y > 0:
				play("delete-sound", "delete-text", config.get("new line-text", "line feed"))
			else:
				play("edge text-sound", None)

		# Process Pygame events in exact order so Vietnamese IME (UniKey/EVKey) Backspace + TextInput works seamlessly
		for event in pygame.event.get():
			if event.type == pygame.TEXTEDITING:
				editing = event.text

			elif event.type == pygame.TEXTINPUT and not ctrl:
				editing = ""
				insert_text(event.text)

			elif event.type == pygame.KEYDOWN:
				if event.key == pygame.K_BACKSPACE:
					if not has_perm(1):
						pass
					elif has_selection():
						save_state()
						delete_selection()
					elif x > 0:
						save_state()
						lines[y] = lines[y][:x-1] + lines[y][x:]
						x -= 1
					elif y > 0:
						save_state()
						x = len(lines[y-1])
						lines[y-1] += lines[y]
						lines.pop(y)
						y -= 1

				elif event.key == pygame.K_DELETE:
					if not has_perm(1):
						play("cannot delete-sound", "cannot delete-text")
					elif has_selection():
						save_state()
						deleted = delete_selection()
						play("delete-sound", "delete-text", deleted if has_perm(2) else config.get("cannot read-text", "star"))
					elif x < len(lines[y]):
						save_state()
						ch = lines[y][x]
						lines[y] = lines[y][:x] + lines[y][x+1:]
						play("delete-sound", "delete-text", ch if has_perm(2) else config.get("cannot read-text", "star"))
					elif y < len(lines) - 1:
						save_state()
						lines[y] += lines[y+1]
						lines.pop(y+1)
						play("delete-sound", "delete-text", config.get("new line-text", "line feed"))
					else:
						play("edge text-sound", None)

		# --- Clipboard & History Shortcuts (Ctrl+A, Z, Y, X, C, V) ---
		if ctrl and bf.keyPressed("a"):
			starty, startx = 0, 0
			endy = len(lines) - 1
			endx = len(lines[endy])
			y, x = endy, endx
			announce_selection()
			continue

		if ctrl and bf.keyPressed("z"):
			if has_perm(10):
				if undo_stack:
					redo_stack.append((lines.copy(), x, y))
					lines, x, y = undo_stack.pop()
					clear_selection()
					play("undo-sound", None)
					say_content(lines[y])
				else:
					play("edge text-sound", None)
			else:
				play("cannot undo-sound", "cannot undo-text")
			continue

		if ctrl and bf.keyPressed("y"):
			if has_perm(11):
				if redo_stack:
					undo_stack.append((lines.copy(), x, y))
					lines, x, y = redo_stack.pop()
					clear_selection()
					play("redo-sound", None)
					say_content(lines[y])
				else:
					play("edge text-sound", None)
			else:
				play("cannot redo-sound", "cannot redo-text")
			continue

		if ctrl and bf.keyPressed("c"):
			if has_perm(13) and has_perm(2):
				sel = get_selected_text() or lines[y]
				try: pygame.scrap.put(pygame.SCRAP_TEXT, sel.encode("utf-8"))
				except Exception: pass
				play("copy-sound", None)
			else:
				play("cannot copy-sound", "cannot copy-text")
			continue

		if ctrl and bf.keyPressed("x"):
			if has_perm(1) and has_perm(12) and has_perm(13) and has_perm(2):
				if not has_selection():
					starty = endy = y
					startx, endx = 0, len(lines[y])
				sel = get_selected_text()
				if sel:
					save_state()
					try: pygame.scrap.put(pygame.SCRAP_TEXT, sel.encode("utf-8"))
					except Exception: pass
					delete_selection()
					play("cut-sound", None)
			else:
				play("cannot cut-sound", "cannot cut-text")
			continue

		if ctrl and bf.keyPressed("v"):
			if has_perm(14) and has_perm(0):
				try:
					raw = pygame.scrap.get(pygame.SCRAP_TEXT)
					clip = raw.decode("utf-8").rstrip("\x00") if raw else ""
				except Exception:
					clip = ""
				if clip and insert_text(clip, is_paste=True):
					play("paste-sound", None)
					say_content(clip)
			else:
				play("cannot paste-sound", "cannot paste-text")
			continue

		# --- Enter & New Line ---
		if bf.keyPressed("enter"):
			if shift and get_data:
				if has_perm(0) and has_perm(6):
					save_state()
					if has_selection(): delete_selection()
					right_part = lines[y][x:]
					lines[y] = lines[y][:x]
					lines.insert(y + 1, right_part)
					y += 1
					x = 0
					play("new line-sound", None)
					say_content(lines[y])
				else:
					play("cannot write-sound", "cannot write-text")
			elif get_data:
				play("confirm-sound", None)
				pygame.key.stop_text_input()
				bf.wait(5)
				return "\n".join(lines)

		# --- Cursor Navigation & Shift Selection ---
		def move_cursor(new_y, new_x, sound_key="move text-sound"):
			nonlocal x, y, startx, starty, endx, endy
			if shift:
				if startx == -1:
					starty, startx = y, x
				y, x = new_y, new_x
				endy, endx = y, x
				play(sound_key, None)
				announce_selection()
			else:
				clear_selection(announce=True)
				y, x = new_y, new_x
				play(sound_key, None)

		if bf.keyPressing("left", 200):
			if ctrl:
				if x > 0:
					nx = x - 1
					while nx > 0 and lines[y][nx - 1] == " ": nx -= 1
					while nx > 0 and lines[y][nx - 1] != " ": nx -= 1
					word = lines[y][nx:x].strip()
					move_cursor(y, nx)
					if not shift: say_content(word)
				elif y > 0:
					move_cursor(y - 1, len(lines[y - 1]))
					if not shift: bf.say(config.get("new line-text", "line feed"))
				else:
					play("edge text-sound", None)
			else:
				if x > 0:
					move_cursor(y, x - 1)
					if not shift: say_content(lines[y][x], is_char=True)
				elif y > 0:
					move_cursor(y - 1, len(lines[y - 1]))
					if not shift: bf.say(config.get("new line-text", "line feed"))
				else:
					clear_selection(announce=True)
					play("edge text-sound", None)
					say_content(lines[y][x] if lines[y] and x < len(lines[y]) else "", is_char=True)

		if bf.keyPressing("right", 200):
			if ctrl:
				if x < len(lines[y]):
					nx = x
					while nx < len(lines[y]) and lines[y][nx] != " ": nx += 1
					while nx < len(lines[y]) and lines[y][nx] == " ": nx += 1
					word = lines[y][x:nx].strip()
					move_cursor(y, nx)
					if not shift: say_content(word)
				elif y < len(lines) - 1:
					move_cursor(y + 1, 0)
					if not shift: bf.say(config.get("new line-text", "line feed"))
				else:
					play("edge text-sound", None)
			else:
				if x < len(lines[y]):
					ch = lines[y][x]
					move_cursor(y, x + 1)
					if not shift: say_content(ch, is_char=True)
				elif y < len(lines) - 1:
					move_cursor(y + 1, 0)
					if not shift: bf.say(config.get("new line-text", "line feed"))
				else:
					clear_selection(announce=True)
					play("edge text-sound", None)
					say_content(lines[y][x-1] if lines[y] and x > 0 else "", is_char=True)

		if bf.keyPressing("up", 200):
			if y > 0:
				move_cursor(y - 1, min(x, len(lines[y - 1])), "move line-sound")
				if not shift: say_content(lines[y])
			else:
				clear_selection(announce=True)
				play("edge text-sound", None)
				say_content(lines[y])

		if bf.keyPressing("down", 200):
			if y < len(lines) - 1:
				move_cursor(y + 1, min(x, len(lines[y + 1])), "move line-sound")
				if not shift: say_content(lines[y])
			else:
				clear_selection(announce=True)
				play("edge text-sound", None)
				say_content(lines[y])

		if bf.keyPressed("home"):
			ny = 0 if ctrl else y
			move_cursor(ny, 0)
			if not shift:
				say_content(lines[ny][0] if lines[ny] else "", is_char=True)

		if bf.keyPressed("end"):
			ny = len(lines) - 1 if ctrl else y
			move_cursor(ny, len(lines[ny]))
			if not shift:
				say_content(lines[ny][-1] if lines[ny] else "", is_char=True)

		# --- Exit & Read Full Text ---
		if bf.keyPressed("exit"):
			play("exit-sound", None)
			pygame.key.stop_text_input()
			bf.wait(5)
			return None

		if bf.keyPressed("lalt"):
			say_content("\n".join(lines))