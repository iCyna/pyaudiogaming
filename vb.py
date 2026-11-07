# -*- coding: utf-8 -*-
# virtual box multifunctional
# copyright 2025 belong ihcyna (Labubu)<phucnggo29@gmail.com>.

import os, time, pygame
from copy import deepcopy
from .sound_pool import playsingle
from .utils import get_window
from . import system

INPUT_CONFIG = {
	"callback-default": None, "read char": True, "read word": True, "readonly": False,
	"multiline": True, "number_only": False, "max_length": 0, "placeholder": "",
	"announce_type": False, "suggestions": [], "autocomplete": True,
	"edit-text": "edit", "readonly-text": "read only", "multiline-text": "multi line",
	"password-text": "password", "number-text": "number only",
	"suggestion-text": "%d suggestions, %s",
	"permissions": [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
	"blank-sound": None, "write-sound": None, "capital write-sound": None, "delete-sound": None,
	"space-sound": None, "new line-sound": None, "open-sound": None, "confirm-sound": None,
	"exit-sound": None, "edge text-sound": None, "move text-sound": None, "move line-sound": None,
	"undo-sound": None, "redo-sound": None, "cut-sound": None, "copy-sound": None, "paste-sound": None,
	"suggest-sound": None, "cannot write-sound": None, "cannot capital write-sound": None,
	"cannot read-sound": None, "cannot delete-sound": None, "cannot undo-sound": None,
	"cannot redo-sound": None, "cannot cut-sound": None, "cannot copy-sound": None, "cannot paste-sound": None,
	"blank-text": "blank", "space-text": "%s space", "new line-text": "line feed",
	"capital-text": "CAPITAL %s", "delete-text": "%s deleting", "unselected-text": "Unselected",
	"select all-text": "%s selected", "select max-text": "%d characters", "select max all-text": "all",
	"select max all": -1, "select all-sound": None, "cannot write-text": "read only",
	"cannot capital write-text": "", "cannot read-text": "star", "cannot delete-text": "read only",
	"cannot undo-text": "", "cannot redo-text": "", "cannot cut-text": "No cutting allowed here",
	"cannot copy-text": "No copying allowed here", "cannot paste-text": "No pasting allowed here",
}

FORM_CONFIG = {
	"permissions": ["read", "move", "enter", "edit", "check", "cancel", "context"],
	"button-text": "button", "check-text": "check box", "list-text": "list", "input-text": "edit",
	"readonly-text": "read only", "multiline-text": "multi line", "number-text": "number only",
	"radio-text": "radio button", "combo-text": "combo box", "tree-text": "tree view",
	"dir_tree-text": "folder tree view", "slider-text": "slider", "tab-text": "tab",
	"progress-text": "progress bar", "table-text": "table", "dialog-text": "dialog",
	"heading-text": "heading level %d", "quote-text": "block quote", "note-text": "note",
	"emphasis-text": "emphasis", "frame-text": "grouping", "live-text": "alert",
	"selected-text": "selected", "context-text": "context menu", "checked-text": "checked",
	"unchecked-text": "not checked", "collapsed-text": "collapsed", "expanded-text": "expanded",
	"level-text": "level %d", "row-text": "row %d", "col-text": "column %d",
	"table-size-text": "with %d rows and %d columns", "out-of-table-text": "out of table",
	"edge-table-text": "edge of table", "blank-text": "blank", "star-text": "star",
	"sep-text": ", ", "np-text": "%d of %d", "readNP": False, "password-text": "password",
	"readonly": False, "multiline": False, "number_only": False, "max_length": 0, "placeholder": "",
	"tab_page": None, "auto_submit": True, "adjacent_submit": True,
	"table_read_header": True, "table_read_coords": True, "table_cell_border": True,
	"color": None, "bg_color": None, "border_color": None, "font": None, "font_size": 17,
	"pos": None, "size": None, "border": 1, "margin": 6, "padding": 10, "level": 1,
	"focus-sound": None, "enter-sound": None, "check-sound": None, "edit-sound": None,
	"cancel-sound": None, "open-sound": None, "expand-sound": None, "collapse-sound": None,
	"context-sound": None, "slider-sound": None, "tab-sound": None, "progress-sound": None,
	"table-sound": None, "live-sound": None, "dialog-sound": None,
	"label": "", "hint": "", "input": {}, "menu": {}, "context": [],
}


class _TouchEngine:
	"""Android TalkBack touch & double-tap-hold detector."""
	def __init__(self):
		self.taps, self.down_t, self.down_pos, self.holding, self.double_hold = [], 0.0, (0, 0), False, False

	def update(self, events):
		now, acts, self.double_hold = time.time(), [], False
		for e in events:
			if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
				self.down_t, self.down_pos, self.holding = now, e.pos, True
				self.taps = [t for t in self.taps if now - t[0] < 0.45] + [(now, e.pos)]
			elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
				if self.holding and now - self.down_t < 0.4:
					acts.append(("double_tap" if len(self.taps) >= 2 else "tap", e.pos))
					if len(self.taps) >= 2: self.taps.clear()
				self.holding = False
			elif e.type == pygame.MOUSEWHEEL:
				acts.append(("scroll", -e.y))
		# Double-tap and hold (>0.45s on 2nd tap) triggers context menu like Android/iOS
		if self.holding and len(self.taps) >= 2 and (now - self.down_t >= 0.45):
			self.double_hold, self.holding = True, False
			self.taps.clear()
			acts.append(("context_hold", self.down_pos))
		return acts


class _Renderer:
	"""Android Material Dark GUI renderer for Input, Message, Dialog, Table and Form."""
	_fonts, _rects = {}, {}

	@classmethod
	def get_font(cls, size=17, bold=False, italic=False, name=None):
		if not pygame.font.get_init(): pygame.font.init()
		k = (name, size, bold, italic)
		if k not in cls._fonts:
			f_list = [name] if name else ["segoeui", "roboto", "arial", "tahoma", "consolas", "sans"]
			cls._fonts[k] = pygame.font.SysFont(f_list, size, bold=bold, italic=italic)
		return cls._fonts[k]

	@classmethod
	def get_surface(cls, wnd):
		for a in ("screen", "surface", "display", "surf", "window"):
			v = getattr(wnd, a, None)
			if isinstance(v, pygame.Surface): return v
		return pygame.display.get_surface()

	@classmethod
	def draw_message(cls, wnd, text, title="Dialog", buttons=("OK",), btn_idx=0):
		surf = cls.get_surface(wnd)
		if not surf: return {}
		w, h = surf.get_size()
		surf.fill((16, 18, 24))
		bw, bh = min(640, w - 40), min(300, h - 40)
		bx, by = (w - bw) // 2, (h - bh) // 2
		pygame.draw.rect(surf, (28, 31, 42), (bx, by, bw, bh), border_radius=12)
		pygame.draw.rect(surf, (95, 160, 255), (bx, by, bw, bh), 2, border_radius=12)
		surf.blit(cls.get_font(19, True).render(str(title), True, (120, 185, 255)), (bx + 22, by + 16))
		fnt, words, lines, cur = cls.get_font(17), str(text).split(" "), [], ""
		for wd in words:
			t = (cur + " " + wd).strip()
			if fnt.size(t)[0] <= bw - 44: cur = t
			else: lines.append(cur); cur = wd
		if cur: lines.append(cur)
		ty = by + 54
		for ln in lines[:6]:
			surf.blit(fnt.render(ln, True, (235, 238, 245)), (bx + 22, ty)); ty += 26
		btn_rects = {}
		total_w = len(buttons) * 108 - 12
		sx = bx + (bw - total_w) // 2
		for i, btxt in enumerate(buttons):
			r = pygame.Rect(sx + i * 108, by + bh - 50, 96, 36)
			foc = (i == btn_idx)
			pygame.draw.rect(surf, (65, 130, 230) if foc else (42, 46, 60), r, border_radius=8)
			pygame.draw.rect(surf, (255, 220, 90) if foc else (90, 100, 125), r, 2 if foc else 1, border_radius=8)
			ts = cls.get_font(16, True).render(str(btxt), True, (255, 255, 255))
			surf.blit(ts, (r.centerx - ts.get_width() // 2, r.centery - ts.get_height() // 2))
			btn_rects[i] = r
		pygame.display.flip()
		return btn_rects

	@classmethod
	def draw_input(cls, wnd, title, lines, x, y, norm_sel_fn, has_sel, password, config, suggs=None, s_idx=-1):
		surf = cls.get_surface(wnd)
		if not surf: return {}
		w, h = surf.get_size()
		surf.fill(config.get("bg_color") or (16, 18, 24))
		pad, f_title, f_meta, f_txt = 24, cls.get_font(19, True), cls.get_font(14), cls.get_font(config.get("font_size", 18), name=config.get("font"))
		badges = [config.get("edit-text", "edit")]
		if config.get("readonly") or (0 not in config["permissions"] and -1 not in config["permissions"]): badges.append(config.get("readonly-text", "read only"))
		if password or config.get("password") or (isinstance(config.get("permissions"), (list, tuple, set)) and any(isinstance(x, int) for x in config["permissions"]) and 2 not in config["permissions"] and -1 not in config["permissions"] and not config.get("readonly")): badges.append(config.get("password-text", "password"))
		if config.get("multiline") and (6 in config["permissions"] or -1 not in config["permissions"]): badges.append(config.get("multiline-text", "multi line"))
		if config.get("number_only"): badges.append(config.get("number-text", "number only"))
		surf.blit(f_title.render(f"{title or 'Input'}  [{' | '.join(badges)}]", True, (110, 180, 255)), (pad, pad))

		# Android-style action bar (Copy, Paste, Clear, Done)
		ui_rects = {}
		act_names = [("Copy", "copy"), ("Paste", "paste"), ("All", "all"), ("Done", "done")]
		ax = w - pad - len(act_names) * 74
		for lbl, key in act_names:
			ar = pygame.Rect(ax, pad - 2, 68, 28)
			pygame.draw.rect(surf, (45, 95, 175) if key == "done" else (36, 40, 54), ar, border_radius=6)
			pygame.draw.rect(surf, (100, 150, 230), ar, 1, border_radius=6)
			ts = f_meta.render(lbl, True, (255, 255, 255))
			surf.blit(ts, (ar.centerx - ts.get_width() // 2, ar.centery - ts.get_height() // 2))
			ui_rects[key] = ar; ax += 74

		by, bh = pad + 36, h - pad * 2 - 78
		brect = pygame.Rect(pad, by, w - pad * 2, max(60, bh))
		pygame.draw.rect(surf, (26, 29, 38), brect, border_radius=8)
		pygame.draw.rect(surf, (220, 160, 60) if config.get("readonly") else (90, 160, 250), brect, 2, border_radius=8)
		ui_rects["box"] = brect

		lh = f_txt.get_height() + 6
		max_vis = max(1, (brect.height - 20) // lh)
		s_line = max(0, y - max_vis + 1)
		sy, sx, ey, ex = norm_sel_fn() if has_sel else (-1, -1, -1, -1)

		if len(lines) == 1 and lines[0] == "" and config.get("placeholder"):
			surf.blit(f_txt.render(str(config["placeholder"]), True, (110, 115, 130)), (brect.x + 12, brect.y + 10))

		for idx in range(s_line, min(len(lines), s_line + max_vis)):
			raw = lines[idx]
			disp = ("*" * len(raw)) if (password or config.get("password") or (isinstance(config.get("permissions"), (list, tuple, set)) and any(isinstance(x, int) for x in config["permissions"]) and 2 not in config["permissions"] and -1 not in config["permissions"] and not config.get("readonly"))) else raw
			ly = brect.y + 10 + (idx - s_line) * lh
			if has_sel and sy <= idx <= ey:
				ss, se = (sx if idx == sy else 0), (ex if idx == ey else len(disp))
				px1, px2 = brect.x + 12 + f_txt.size(disp[:ss])[0], brect.x + 12 + f_txt.size(disp[:se])[0]
				pygame.draw.rect(surf, (55, 105, 185), (px1, ly, max(4, px2 - px1), lh - 2))
			surf.blit(f_txt.render(disp, True, config.get("color") or (235, 238, 245)), (brect.x + 12, ly))
			if idx == y:
				cx = brect.x + 12 + f_txt.size(disp[:x])[0]
				pygame.draw.line(surf, (255, 215, 70), (cx, ly + 2), (cx, ly + lh - 4), 2)
				# Android teardrop cursor handle
				pygame.draw.circle(surf, (90, 175, 255), (cx, ly + lh), 5)

		# Autocomplete suggestion chips bar (Android Gboard style)
		if suggs:
			sx_chip = pad
			sy_chip = brect.bottom + 8
			for i, sg in enumerate(suggs[:5]):
				cw = f_meta.size(str(sg))[0] + 24
				crect = pygame.Rect(sx_chip, sy_chip, cw, 26)
				active = (i == s_idx)
				pygame.draw.rect(surf, (60, 120, 215) if active else (34, 38, 50), crect, border_radius=13)
				pygame.draw.rect(surf, (255, 220, 80) if active else (75, 85, 110), crect, 1, border_radius=13)
				surf.blit(f_meta.render(str(sg), True, (255, 255, 255)), (sx_chip + 12, sy_chip + 4))
				ui_rects[f"sug_{i}"] = crect; sx_chip += cw + 8

		st = f"Ln {y + 1}/{len(lines)}, Col {x + 1} | Tab/Down: Suggestions | Enter: Confirm | Esc: Cancel"
		surf.blit(f_meta.render(st, True, (145, 150, 165)), (pad, h - 24))
		pygame.display.flip()
		return ui_rects

	@classmethod
	def draw_form(cls, f):
		surf = cls.get_surface(f.wnd)
		if not surf: return {}
		w, h = surf.get_size()
		surf.fill(f.config.get("bg_color") or (16, 18, 24))
		cls._rects = {"items": {}, "tabs": {}, "combos": {}, "trees": {}, "cells": {}}
		f_title, f_small = cls.get_font(20, True), cls.get_font(14)
		pad = f.config.get("padding", 20)
		ty = pad
		surf.blit(f_title.render(f.config.get("label") or "Form", True, (120, 185, 255)), (pad, ty))
		ty += 32

		vis = f._visible_items()
		if not vis: pygame.display.flip(); return cls._rects
		cur_it = f.items[f.cursor] if f.items else None

		# Draw Tab Bar
		for it in vis:
			if it["kind"] == "tab":
				tx, f_b, f_n = pad, cls.get_font(16, True), cls.get_font(16)
				for tidx, tname in enumerate(it["tabs"]):
					act, foc = (tidx == it["tab_cursor"]), (it is cur_it)
					tw = f_b.size(tname)[0] + 26
					tr = pygame.Rect(tx, ty, tw, 32)
					pygame.draw.rect(surf, (55, 115, 210) if act else (30, 34, 45), tr, border_radius=8)
					pygame.draw.rect(surf, (255, 215, 70) if (act and foc) else ((110, 165, 245) if act else (65, 70, 85)), tr, 2 if act else 1, border_radius=8)
					surf.blit((f_b if act else f_n).render(tname, True, (255, 255, 255) if act else (175, 180, 195)), (tx + 13, ty + 5))
					cls._rects["tabs"][(it["name"], tidx)] = tr; tx += tw + 8
				ty += 40

		avail_h = h - ty - pad - 28
		# Calculate dynamic item heights (tables/trees/expanded combos take more height)
		def _item_h(item):
			if item["config"].get("size"): return item["config"]["size"][1]
			k = item["kind"]
			if k == "table": return min(180, 32 + len(item["rows"]) * 28)
			if k in ("tree", "dir_tree"): return min(160, 32 + min(5, max(1, len(item["flat"]))) * 24)
			if k == "combo" and item.get("expanded"): return 42 + min(4, item["menu"].Len()) * 26
			return 44

		cur_v_idx = vis.index(cur_it) if cur_it in vis else 0
		# Scroll window calculation
		s_idx, acc_h = cur_v_idx, 0
		while s_idx > 0 and acc_h + _item_h(vis[s_idx - 1]) <= avail_h:
			s_idx -= 1; acc_h += _item_h(vis[s_idx])

		idx = s_idx
		while idx < len(vis) and ty < h - pad - 28:
			it = vis[idx]
			foc = (it is cur_it)
			cfg, k = it["config"], it["kind"]
			ih = _item_h(it)
			margin = cfg.get("margin", 6)
			pos, sz = cfg.get("pos"), cfg.get("size")

			# Group inline adjacent button with input/combo on same row if auto-paired
			nxt = vis[idx + 1] if idx + 1 < len(vis) else None
			inline_btn = (k in ("input", "combo") and nxt and nxt["kind"] == "button" and cfg.get("adjacent_submit", True) and not pos)
			rw = (w - pad * 2 - 116) if inline_btn else (sz[0] if sz else w - pad * 2)
			rx, ry = (pos[0] if pos else pad), (pos[1] if pos else ty)
			rect = pygame.Rect(rx, ry, rw, ih - margin)
			cls._rects["items"][it["name"]] = rect

			bg = cfg.get("bg_color") or ((36, 48, 72) if foc else (25, 28, 37))
			b_col = cfg.get("border_color") or ((95, 175, 255) if foc else (52, 58, 74))
			b_w = cfg.get("border", 2 if foc else 1)
			if b_w >= 0:
				pygame.draw.rect(surf, bg, rect, border_radius=8)
				if b_w > 0: pygame.draw.rect(surf, b_col, rect, b_w, border_radius=8)

			fsz = cfg.get("font_size", 19 if k == "heading" else 17)
			fnt = cls.get_font(fsz, bold=(foc or k in ("heading", "emphasis", "button")), italic=(k in ("quote", "note")), name=cfg.get("font"))
			col = cfg.get("color") or ((255, 255, 255) if foc else (215, 220, 230))
			lbl = cfg.get("label") or it["name"]

			if k == "button":
				ts = fnt.render(f"[ {lbl} ]", True, cfg.get("color") or ((255, 230, 105) if foc else (150, 200, 255)))
				surf.blit(ts, (rect.centerx - ts.get_width() // 2, rect.centery - ts.get_height() // 2))
			elif k == "check":
				br = pygame.Rect(rect.x + 14, rect.centery - 10, 20, 20)
				pygame.draw.rect(surf, (45, 50, 65), br, border_radius=4)
				pygame.draw.rect(surf, (130, 185, 255), br, 2, border_radius=4)
				if it["value"]:
					pygame.draw.lines(surf, (90, 240, 130), False, [(br.x + 4, br.centery), (br.centerx - 1, br.bottom - 4), (br.right - 4, br.y + 4)], 3)
				surf.blit(fnt.render(lbl, True, col), (br.right + 12, rect.y + 7))
			elif k in ("slider", "progress"):
				surf.blit(fnt.render(f"{lbl}:", True, col), (rect.x + 14, rect.y + 7))
				bx, bw = rect.x + 200, max(100, rect.width - 310)
				br = pygame.Rect(bx, rect.centery - 5, bw, 10)
				pygame.draw.rect(surf, (50, 56, 72), br, border_radius=5)
				span = (it["max"] - it["min"]) or 1
				ratio = max(0.0, min(1.0, (it["value"] - it["min"]) / span))
				pygame.draw.rect(surf, (75, 215, 135) if k == "progress" else (80, 175, 255), (bx, br.y, int(bw * ratio), 10), border_radius=5)
				if k == "slider": pygame.draw.circle(surf, (255, 225, 90) if foc else (220, 225, 235), (bx + int(bw * ratio), rect.centery), 8)
				v_txt = f"{int(ratio * 100)}%" if (k == "progress" and not it.get("unit")) else f"{it['value']}{it.get('unit', '')}"
				surf.blit(fnt.render(v_txt, True, (130, 220, 255)), (br.right + 12, rect.y + 7))
			elif k == "input":
				tags = f._get_input_type_tags(it)
				rv = str(it["value"] if it["value"] is not None else "")
				dv = (cfg.get("placeholder") or f"<{cfg['blank-text']}>") if rv == "" else ("*" * len(rv) if cfg.get("password") else rv.replace("\n", " ¶ "))
				vc = (130, 135, 150) if rv == "" else (240, 240, 245)
				ls = fnt.render(f"{lbl}: ", True, col)
				surf.blit(ls, (rect.x + 14, rect.y + 7))
				ib = pygame.Rect(rect.x + 16 + ls.get_width(), rect.y + 5, max(60, rect.width - ls.get_width() - 28), rect.height - 10)
				pygame.draw.rect(surf, (16, 18, 26), ib, border_radius=6)
				pygame.draw.rect(surf, (80, 125, 185), ib, 1, border_radius=6)
				surf.blit(cls.get_font(16).render(dv[:38], True, vc), (ib.x + 8, ib.y + 4))
			elif k in ("list", "radio", "combo"):
				cs = it["menu"].getReadStr() if it["menu"].items else cfg["blank-text"]
				pf = "(o)" if k == "radio" else (("▲" if it.get("expanded") else "▼") if k == "combo" else "☰")
				surf.blit(fnt.render(f"{lbl}:  {pf} {cs}", True, col), (rect.x + 14, rect.y + 7))
				if k == "combo" and it.get("expanded") and it["menu"].items:
					m_items = it["menu"].items
					c_cur = it["menu"].cursor
					st_c = max(0, min(c_cur - 1, len(m_items) - 4))
					for ci in range(st_c, min(len(m_items), st_c + 4)):
						cr = pygame.Rect(rect.x + 24, rect.y + 36 + (ci - st_c) * 25, rect.width - 36, 23)
						is_c = (ci == c_cur)
						pygame.draw.rect(surf, (60, 115, 200) if is_c else (32, 36, 48), cr, border_radius=4)
						surf.blit(f_small.render(str(m_items[ci][0]), True, (255, 255, 255) if is_c else (195, 200, 215)), (cr.x + 8, cr.y + 2))
						cls._rects["combos"][(it["name"], ci)] = cr
			elif k in ("tree", "dir_tree"):
				surf.blit(fnt.render(f"{lbl}:", True, col), (rect.x + 14, rect.y + 5))
				fl, tc = it["flat"], it["tree_cursor"]
				st_t = max(0, min(tc - 2, len(fl) - 5))
				for ti in range(st_t, min(len(fl), st_t + 5)):
					ent = fl[ti]
					nd = ent["node"]
					tr = pygame.Rect(rect.x + 14 + (ent["level"] - 1) * 18, rect.y + 30 + (ti - st_t) * 23, rect.width - 28 - (ent["level"] - 1) * 18, 22)
					if ti == tc: pygame.draw.rect(surf, (55, 110, 195), tr, border_radius=4)
					has_c = bool(nd.get("children")) or (k == "dir_tree" and nd.get("is_dir") and not nd.get("loaded"))
					ico = ("[-] " if nd.get("expanded") else "[+] ") if has_c else " •  "
					surf.blit(f_small.render(f"{ico}{nd['label']}", True, (255, 255, 255) if ti == tc else (200, 205, 220)), (tr.x + 6, tr.y + 2))
					cls._rects["trees"][(it["name"], ti)] = tr
			elif k == "table":
				surf.blit(fnt.render(f"{lbl} ({len(it['rows'])}x{len(it['headers'])}):", True, col), (rect.x + 12, rect.y + 4))
				cols_n = max(1, len(it["headers"]))
				cw = (rect.width - 24) // cols_n
				all_r = ([it["headers"]] if it["headers"] else []) + it["rows"]
				sr = max(0, min(it["row"] - 2, len(all_r) - 5))
				for ri in range(sr, min(len(all_r), sr + 5)):
					ry_c = rect.y + 28 + (ri - sr) * 26
					for ci, cell_v in enumerate(all_r[ri][:cols_n]):
						cr = pygame.Rect(rect.x + 12 + ci * cw, ry_c, cw - 2, 24)
						is_sel = (ri == (it["row"] + (1 if it["headers"] else 0)) and ci == it["col"])
						is_hdr = (ri == 0 and bool(it["headers"]))
						pygame.draw.rect(surf, (65, 125, 215) if is_sel else ((42, 48, 66) if is_hdr else (20, 23, 32)), cr, border_radius=3)
						if cfg.get("table_cell_border", True):
							pygame.draw.rect(surf, (255, 220, 80) if is_sel else (70, 80, 105), cr, 2 if is_sel else 1, border_radius=3)
						surf.blit(cls.get_font(14, bold=is_hdr).render(str(cell_v)[:18], True, (255, 255, 255)), (cr.x + 6, cr.y + 3))
						cls._rects["cells"][(it["name"], ri - (1 if it["headers"] else 0), ci)] = cr
			elif k in ("heading", "quote", "note", "emphasis", "frame", "live"):
				if k == "quote": pygame.draw.line(surf, (100, 180, 255), (rect.x + 8, rect.y + 6), (rect.x + 8, rect.bottom - 6), 4)
				prefix = f"H{cfg.get('level', 1)}: " if k == "heading" else ("❝ " if k == "quote" else ("📝 " if k == "note" else ("★ " if k == "emphasis" else "")))
				txt_v = f"{prefix}{lbl}" + (f" - {it['value']}" if it["value"] else "")
				surf.blit(fnt.render(txt_v, True, col), (rect.x + (18 if k == "quote" else 12), rect.y + 7))
			else:
				surf.blit(fnt.render(f"{lbl} ({k})", True, col), (rect.x + 14, rect.y + 7))

			# Render adjacent button inline on right side
			if inline_btn:
				b_it = nxt
				b_foc = (b_it is cur_it)
				brect = pygame.Rect(rect.right + 8, ry, 108, ih - margin)
				cls._rects["items"][b_it["name"]] = brect
				pygame.draw.rect(surf, (55, 120, 215) if b_foc else (38, 68, 120), brect, border_radius=8)
				pygame.draw.rect(surf, (255, 225, 90) if b_foc else (95, 155, 245), brect, 2 if b_foc else 1, border_radius=8)
				blbl = b_it["config"].get("label") or b_it["name"]
				bts = cls.get_font(16, True).render(blbl, True, (255, 255, 255))
				surf.blit(bts, (brect.centerx - bts.get_width() // 2, brect.centery - bts.get_height() // 2))
				idx += 1

			ty += ih; idx += 1

		footer = f"Item {cur_v_idx + 1}/{len(vis)} | Touch/Tab/Arrows: Navigate | Double-Tap Hold: Context Menu"
		surf.blit(f_small.render(footer, True, (140, 145, 165)), (pad, h - 22))
		pygame.display.flip()
		return cls._rects


def _copy(text):
	if system.get_platform()["os"] == "windows":
		try:
			import win32clipboard as clip
			clip.OpenClipboard(); clip.EmptyClipboard(); clip.SetClipboardText(text, clip.CF_UNICODETEXT); clip.CloseClipboard(); return
		except Exception: pass
	pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8") + b"\x00")


def _paste():
	if system.get_platform()["os"] == "windows":
		try:
			import win32clipboard as clip
			clip.OpenClipboard()
			res = clip.GetClipboardData(clip.CF_UNICODETEXT) if clip.IsClipboardFormatAvailable(clip.CF_UNICODETEXT) else ""
			clip.CloseClipboard(); return res
		except Exception: pass
	raw = pygame.scrap.get(pygame.SCRAP_TEXT)
	return raw.decode("utf-8").rstrip("\x00") if raw else ""


def dialog(title="Dialog", text="", buttons=("OK", "Cancel"), default=0, cancel=1, callback=None, window=None):
	"""Interactive modal dialog with multi-button navigation and touch support."""
	wnd = window or get_window()
	idx, touch = max(0, min(default, len(buttons) - 1)), _TouchEngine()
	wnd.say(f"{title} dialog. {text}. {buttons[idx]} button")
	while True:
		wnd.frameUpdate()
		rects = _Renderer.draw_message(wnd, text, title=title, buttons=buttons, btn_idx=idx)
		if callback: callback()
		evs = wnd.events if hasattr(wnd, "events") else pygame.event.get()
		for act, pos in touch.update(evs):
			for bi, r in rects.items():
				if r.collidepoint(pos):
					if act == "tap" and idx != bi: idx = bi; wnd.say(f"{buttons[idx]} button")
					elif act in ("double_tap", "tap") and idx == bi: return buttons[idx]
		if wnd.keyPressed("left") or wnd.keyPressed("up") or (wnd.keyPressed("tab") and wnd.keyPressing("lshift")):
			idx = (idx - 1) % len(buttons); wnd.say(f"{buttons[idx]} button")
		elif wnd.keyPressed("right") or wnd.keyPressed("down") or wnd.keyPressed("tab"):
			idx = (idx + 1) % len(buttons); wnd.say(f"{buttons[idx]} button")
		elif wnd.keyPressed("enter") or wnd.keyPressed("space"): return buttons[idx]
		elif wnd.keyPressed("exit") or wnd.keyPressed("esc"):
			return buttons[cancel] if 0 <= cancel < len(buttons) else None


def message(m, callback=None, open=None, move=None, close=None, window=None):
	wnd = window or get_window()
	wnd.say(m)
	if open: playsingle(open)
	touch = _TouchEngine()
	while True:
		wnd.frameUpdate()
		rects = _Renderer.draw_message(wnd, m)
		if callback: callback()
		evs = wnd.events if hasattr(wnd, "events") else pygame.event.get()
		if any(a in ("tap", "double_tap") and rects.get(0) and rects[0].collidepoint(p) for a, p in touch.update(evs)):
			if close: playsingle(close)
			break
		if any(wnd.keyPressed(k) for k in ("left", "right", "up", "down")):
			if move: playsingle(move)
			wnd.say(m)
		if wnd.keyPressed("enter") or wnd.keyPressed("exit") or wnd.keyPressed("esc"):
			if close: playsingle(close)
			break


def get_conput(name, key, fallback=None):
	try: return INPUT_CONFIG.get(f"{key}-{name}", fallback) if key != "" else {k: v for k, v in INPUT_CONFIG.items() if f"-{name}" in k}
	except Exception: return fallback


def set_conput(data, fallback={}):
	try: INPUT_CONFIG.update(data); return INPUT_CONFIG
	except Exception: return fallback


def _build_input_announcement(title, text, password, config):
	parts = [str(title)] if title else []
	if config.get("announce_type"):
		pms = config["permissions"]
		if password or config.get("password") or (isinstance(pms, (list, tuple, set)) and any(isinstance(x, int) for x in pms) and 2 not in pms and -1 not in pms and not config.get("readonly")): parts.append(config.get("password-text", "password"))
		parts.append(config.get("edit-text", "edit"))
		if config.get("readonly") or (0 not in pms and -1 not in pms): parts.append(config.get("readonly-text", "read only"))
		if config.get("number_only"): parts.append(config.get("number-text", "number only"))
		if config.get("multiline") and (6 in pms or -1 in pms): parts.append(config.get("multiline-text", "multi line"))
		val = str(text if text is not None else "")
		if val == "":
			if config.get("placeholder"): parts.append(str(config["placeholder"]))
			parts.append(config.get("blank-text", "blank"))
		elif password or config.get("password") or (isinstance(pms, (list, tuple, set)) and any(isinstance(x, int) for x in pms) and 2 not in pms and -1 not in pms and not config.get("readonly")):
			parts.append(" ".join([config.get("cannot read-text", "star")] * len(val)))
		else: parts.append(val)
	return ", ".join(p for p in parts if p != "")


def _input(title="", text="", callback=None, password=False, get_data=True, new_config=None, window=None):
	bf = window or get_window()
	if bf is None: raise RuntimeError("Create a window before text input")
	config = {**deepcopy(INPUT_CONFIG), **(new_config or {})}
	callback = callback or config.get("callback-default")

	# Filter permissions based on flags
	pms = list(range(15)) if -1 in config["permissions"] else list(config["permissions"])
	for cond, rem in ((password, (-1, 2, 12, 13)), (config.get("readonly"), (-1, 0, 1, 10, 11, 12, 14)), (not config.get("multiline", True), (-1, 6)), (config.get("number_only"), (-1, 3, 4, 5, 7, 8))):
		if cond: pms = [p for p in pms if p not in rem]
	config["permissions"] = pms
	has_perm = lambda p: -1 in pms or p in pms

	def play(snd_k, txt_k=None, *args):
		if config.get(snd_k): playsingle(config[snd_k])
		elif txt_k and config.get(txt_k):
			t = config[txt_k]
			if args:
				try: t = t % args
				except TypeError: pass
			if t != "": bf.say(t)

	def say_content(txt, is_char=False):
		if not txt: play("blank-sound", "blank-text"); return
		if not has_perm(2):
			if config.get("cannot read-sound"): playsingle(config["cannot read-sound"])
			m = config.get("cannot read-text", "star")
			bf.say(m if (is_char or len(txt) == 1) else " ".join([m] * len(txt))); return
		if is_char and len(txt) == 1:
			bf.say((config.get("space-text", "%s space") % "") if txt == " " else ((config.get("capital-text", "CAPITAL %s") % txt) if txt.isupper() else txt))
		else: bf.say(txt)

	try:
		if not pygame.scrap.get_init(): pygame.scrap.init()
	except Exception: pass

	lines = text.split("\n") if text else [""]
	y, x = len(lines) - 1, len(lines[-1])
	startx = endx = starty = endy = -1
	editing, undo_stack, redo_stack = "", [], []
	suggs, s_idx, touch = [], -1, _TouchEngine()

	def update_suggestions():
		nonlocal suggs, s_idx
		pool = config.get("suggestions") or []
		if not pool or not config.get("autocomplete", True): suggs, s_idx = [], -1; return
		cur_w = lines[y][:x].split(" ")[-1].lower()
		full_l = lines[y].strip().lower()
		suggs = [str(s) for s in pool if (cur_w and str(s).lower().startswith(cur_w)) or (full_l and str(s).lower().startswith(full_l))][:6]
		s_idx = -1
		if suggs:
			play("suggest-sound", None)
			bf.say(config.get("suggestion-text", "%d suggestions, %s") % (len(suggs), suggs[0]))

	def apply_suggestion(idx):
		nonlocal x
		if 0 <= idx < len(suggs):
			chosen = suggs[idx]
			save_state()
			prefix = lines[y][:x]
			sp = prefix.rfind(" ")
			lines[y] = (prefix[:sp + 1] if sp != -1 else "") + chosen + lines[y][x:]
			x = (sp + 1 if sp != -1 else 0) + len(chosen)
			bf.say(chosen); suggs.clear(); return True
		return False

	def save_state():
		undo_stack.append((lines.copy(), x, y))
		if len(undo_stack) > 100: undo_stack.pop(0)
		redo_stack.clear()

	has_sel = lambda: startx != -1 and (startx != endx or starty != endy)
	norm_sel = lambda: (starty, startx, endy, endx) if (starty < endy or (starty == endy and startx <= endx)) else (endy, endx, starty, startx)

	def clear_sel(announce=False):
		nonlocal startx, endx, starty, endy
		if has_sel() and announce: play(None, "unselected-text")
		startx = endx = starty = endy = -1

	def get_sel():
		if not has_sel(): return ""
		sy, sx, ey, ex = norm_sel()
		return lines[sy][sx:ex] if sy == ey else "\n".join([lines[sy][sx:]] + lines[sy + 1:ey] + [lines[ey][:ex]])

	def announce_sel():
		s = get_sel()
		if not s: return
		if config.get("select all-sound"): playsingle(config["select all-sound"])
		mc, n, ft = config.get("select max all", -1), len(s), "\n".join(lines)
		if mc == 0 or (s == ft and mc == -1 and n <= 500):
			lbl = config.get("select max all-text", "all") if mc == 0 else (s if has_perm(2) else config.get("select max-text", "%d characters") % n)
		elif (mc == -1 and n > 500) or (mc > 0 and n >= mc) or not has_perm(2): lbl = config.get("select max-text", "%d characters") % n
		else: lbl = s
		bf.say(config.get("select all-text", "%s selected") % lbl)

	def del_sel():
		nonlocal x, y
		if not has_sel(): return False
		sy, sx, ey, ex = norm_sel()
		d = get_sel()
		if sy == ey: lines[sy] = lines[sy][:sx] + lines[sy][ex:]
		else: lines[sy] = lines[sy][:sx] + lines[ey][ex:]; del lines[sy + 1:ey + 1]
		y, x = sy, sx; clear_sel(); return d

	def check_perm(ch):
		if has_perm(-1): return True, False
		if not has_perm(0): return False, False
		if ch == "\n": return has_perm(6), False
		if ch == " ": return has_perm(5), False
		if ch.isdigit(): return has_perm(9), False
		if ch.isalpha():
			if not has_perm(8): return False, False
			if ch.isupper() and not has_perm(3): return False, True
			if not ch.isascii() and not has_perm(4): return False, False
			return True, False
		return has_perm(7), False

	def insert_text(txt, is_paste=False):
		nonlocal x, y
		v_chars = []
		for ch in txt:
			if ch == "\r": continue
			ok, cap_d = check_perm(ch)
			if ok: v_chars.append(ch)
			else: play("cannot capital write-sound" if cap_d else "cannot write-sound", "cannot capital write-text" if cap_d else "cannot write-text")
		if has_sel() and not has_perm(1): play("cannot delete-sound", "cannot delete-text"); return False
		ml = int(config.get("max_length") or 0)
		if ml > 0:
			rem = max(0, ml - (len("\n".join(lines)) - len(get_sel())))
			if rem == 0: play("edge text-sound", None); return False
			v_chars = v_chars[:rem]
		vs = "".join(v_chars)
		if not vs: return False
		save_state(); del_sel()
		pts = vs.split("\n")
		if len(pts) == 1: lines[y] = lines[y][:x] + vs + lines[y][x:]; x += len(vs)
		else:
			rp = lines[y][x:]; lines[y] = lines[y][:x] + pts[0]
			for i, p in enumerate(pts[1:], 1): lines.insert(y + i, p)
			y += len(pts) - 1; x = len(pts[-1]); lines[y] += rp
		if not is_paste:
			if vs.isupper() and len(vs) == 1:
				play("capital write-sound", "capital-text", vs if has_perm(2) else config.get("cannot read-text", "star"))
				if config.get("read char"): say_content(vs)
			elif vs == " ":
				wds = lines[y][:x - 1].split() if config.get("read word") else []
				play("space-sound", "space-text" if wds else None, (wds[-1] if has_perm(2) else config.get("cannot read-text", "star")) if wds else None)
			else:
				play("write-sound", None)
				if config.get("read char"): say_content(vs)
		update_suggestions()
		return True

	play("open-sound", None)
	init_sp = _build_input_announcement(title, text, password, config)
	if init_sp: bf.say(init_sp)

	while True:
		bf.frameUpdate()
		ui_rects = config["draw_callback"](lines, x, y, norm_sel, has_sel(), password, config) if config.get("draw_callback") else _Renderer.draw_input(bf, title, lines, x, y, norm_sel, has_sel(), password, config, suggs, s_idx)
		if callback: callback()
		ctrl = bf.keyPressing("lcontrol") or bf.keyPressing("rcontrol")
		shift = bf.keyPressing("lshift") or bf.keyPressing("rshift")

		if bf.keyPressed("backspace"):
			if not has_perm(1): play("cannot delete-sound", "cannot delete-text")
			elif has_sel(): play("delete-sound", "delete-text", get_sel() if has_perm(2) else config.get("cannot read-text", "star"))
			elif x > 0: play("delete-sound", "delete-text", lines[y][x - 1] if has_perm(2) else config.get("cannot read-text", "star"))
			elif y > 0: play("delete-sound", "delete-text", config.get("new line-text", "line feed"))
			else: play("edge text-sound", None)

		evs = bf.events if hasattr(bf, "events") else pygame.event.get()
		for act, pos in touch.update(evs):
			if act in ("tap", "double_tap") and ui_rects:
				if ui_rects.get("done") and ui_rects["done"].collidepoint(pos): play("confirm-sound", None); return "\n".join(lines)
				if ui_rects.get("copy") and ui_rects["copy"].collidepoint(pos) and has_perm(13): _copy(get_sel() or lines[y]); play("copy-sound", None)
				if ui_rects.get("paste") and ui_rects["paste"].collidepoint(pos) and has_perm(14):
					c = _paste()
					if c and insert_text(c, True): play("paste-sound", None); say_content(c)
				if ui_rects.get("all") and ui_rects["all"].collidepoint(pos):
					starty, startx, endy, endx = 0, 0, len(lines) - 1, len(lines[-1]); y, x = endy, endx; announce_sel()
				for i in range(len(suggs)):
					if ui_rects.get(f"sug_{i}") and ui_rects[f"sug_{i}"].collidepoint(pos): apply_suggestion(i); break
				if ui_rects.get("box") and ui_rects["box"].collidepoint(pos):
					f_txt = _Renderer.get_font(config.get("font_size", 18), name=config.get("font"))
					lh = f_txt.get_height() + 6
					ny = max(0, min(len(lines) - 1, (pos[1] - ui_rects["box"].y - 10) // lh))
					rel_x, best_x = pos[0] - ui_rects["box"].x - 12, 0
					for ci in range(len(lines[ny]) + 1):
						if f_txt.size(lines[ny][:ci])[0] <= rel_x: best_x = ci
					y, x = ny, best_x; clear_sel(); say_content(lines[y][x] if x < len(lines[y]) else lines[y], is_char=(x < len(lines[y])))

		for event in evs:
			if event.type == pygame.QUIT: return None
			if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
				if suggs and not (getattr(event, "mod", 0) & pygame.KMOD_SHIFT):
					s_idx = (s_idx + 1) % len(suggs); bf.say(suggs[s_idx]); continue
				if config.get("tab exit"):
					config["tab exit"](-1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1)
					return "\n".join(lines)
			if event.type == pygame.TEXTEDITING: editing = event.text
			elif event.type == pygame.TEXTINPUT and not ctrl: editing = ""; insert_text(event.text)
			elif event.type == pygame.KEYDOWN:
				if event.key == pygame.K_BACKSPACE and has_perm(1):
					if has_sel(): save_state(); del_sel()
					elif x > 0:
						save_state(); nx = x - 1
						if getattr(event, "mod", 0) & pygame.KMOD_CTRL:
							while nx > 0 and lines[y][nx].isspace(): nx -= 1
							while nx > 0 and not lines[y][nx - 1].isspace(): nx -= 1
						lines[y] = lines[y][:nx] + lines[y][x:]; x = nx
					elif y > 0: save_state(); x = len(lines[y - 1]); lines[y - 1] += lines[y]; lines.pop(y); y -= 1
					update_suggestions()
				elif event.key == pygame.K_DELETE:
					if not has_perm(1): play("cannot delete-sound", "cannot delete-text")
					elif has_sel():
						save_state(); d = del_sel(); play("delete-sound", "delete-text", d if has_perm(2) else config.get("cannot read-text", "star"))
					elif x < len(lines[y]):
						save_state(); ch, nx = lines[y][x], x + 1
						if getattr(event, "mod", 0) & pygame.KMOD_CTRL:
							while nx < len(lines[y]) and not lines[y][nx].isspace(): nx += 1
							while nx < len(lines[y]) and lines[y][nx].isspace(): nx += 1
						lines[y] = lines[y][:x] + lines[y][nx:]
						play("delete-sound", "delete-text", ch if has_perm(2) else config.get("cannot read-text", "star"))
					elif y < len(lines) - 1:
						save_state(); lines[y] += lines[y + 1]; lines.pop(y + 1); play("delete-sound", "delete-text", config.get("new line-text", "line feed"))
					else: play("edge text-sound", None)
					update_suggestions()

		if ctrl and bf.keyPressed("a"):
			starty, startx, endy = 0, 0, len(lines) - 1; endx = len(lines[endy]); y, x = endy, endx; announce_sel(); continue
		if ctrl and bf.keyPressed("z") and not shift:
			if has_perm(10):
				if undo_stack: redo_stack.append((lines.copy(), x, y)); lines, x, y = undo_stack.pop(); clear_sel(); play("undo-sound", None); say_content(lines[y])
				else: play("edge text-sound", None)
			else: play("cannot undo-sound", "cannot undo-text")
			continue
		if ctrl and (bf.keyPressed("y") or (shift and bf.keyPressed("z"))):
			if has_perm(11):
				if redo_stack: undo_stack.append((lines.copy(), x, y)); lines, x, y = redo_stack.pop(); clear_sel(); play("redo-sound", None); say_content(lines[y])
				else: play("edge text-sound", None)
			else: play("cannot redo-sound", "cannot redo-text")
			continue
		if ctrl and bf.keyPressed("c"):
			if has_perm(13) and has_perm(2):
				try: _copy(get_sel() or lines[y])
				except Exception: pass
				play("copy-sound", None)
			else: play("cannot copy-sound", "cannot copy-text")
			continue
		if ctrl and bf.keyPressed("x"):
			if all(has_perm(p) for p in (1, 2, 12, 13)):
				if not has_sel(): starty = endy = y; startx, endx = 0, len(lines[y])
				s = get_sel()
				if s:
					save_state()
					try: _copy(s)
					except Exception: pass
					del_sel(); play("cut-sound", None)
			else: play("cannot cut-sound", "cannot cut-text")
			continue
		if ctrl and bf.keyPressed("v"):
			if has_perm(14) and has_perm(0):
				c = _paste()
				if c and insert_text(c, True): play("paste-sound", None); say_content(c)
			else: play("cannot paste-sound", "cannot paste-text")
			continue

		if bf.keyPressed("enter") and not editing:
			if suggs and s_idx >= 0: apply_suggestion(s_idx); continue
			if shift and get_data:
				if has_perm(0) and has_perm(6):
					save_state(); del_sel(); rp = lines[y][x:]; lines[y] = lines[y][:x]; lines.insert(y + 1, rp); y += 1; x = 0
					play("new line-sound", None); say_content(lines[y])
				else: play("cannot write-sound", "cannot write-text")
			elif get_data:
				play("confirm-sound", None)
				if config.get("enter_submit"): config["enter_submit"]()
				return "\n".join(lines)

		def move_c(ny, nx, snd="move text-sound"):
			nonlocal x, y, startx, starty, endx, endy
			if shift:
				if startx == -1: starty, startx = y, x
				y, x = ny, nx; endy, endx = y, x; play(snd, None); announce_sel()
			else: clear_sel(True); y, x = ny, nx; play(snd, None)

		if bf.keyPressing("left", 200):
			if ctrl:
				if x > 0:
					nx = x - 1
					while nx > 0 and lines[y][nx - 1] == " ": nx -= 1
					while nx > 0 and lines[y][nx - 1] != " ": nx -= 1
					w_s = lines[y][nx:x].strip(); move_c(y, nx)
					if not shift: say_content(w_s)
				elif y > 0: move_c(y - 1, len(lines[y - 1])); (not shift and bf.say(config.get("new line-text", "line feed")))
				else: play("edge text-sound", None)
			elif x > 0: move_c(y, x - 1); (not shift and say_content(lines[y][x], True))
			elif y > 0: move_c(y - 1, len(lines[y - 1])); (not shift and bf.say(config.get("new line-text", "line feed")))
			else: clear_sel(True); play("edge text-sound", None); say_content(lines[y][x] if lines[y] and x < len(lines[y]) else "", True)

		if bf.keyPressing("right", 200):
			if ctrl:
				if x < len(lines[y]):
					nx = x
					while nx < len(lines[y]) and lines[y][nx] != " ": nx += 1
					while nx < len(lines[y]) and lines[y][nx] == " ": nx += 1
					w_s = lines[y][x:nx].strip(); move_c(y, nx)
					if not shift: say_content(w_s)
				elif y < len(lines) - 1: move_c(y + 1, 0); (not shift and bf.say(config.get("new line-text", "line feed")))
				else: play("edge text-sound", None)
			elif x < len(lines[y]): ch = lines[y][x]; move_c(y, x + 1); (not shift and say_content(ch, True))
			elif y < len(lines) - 1: move_c(y + 1, 0); (not shift and bf.say(config.get("new line-text", "line feed")))
			else: clear_sel(True); play("edge text-sound", None); say_content(lines[y][x - 1] if lines[y] and x > 0 else "", True)

		if bf.keyPressing("up", 200):
			if suggs and s_idx >= 0: s_idx = (s_idx - 1) % len(suggs); bf.say(suggs[s_idx])
			elif y > 0: move_c(y - 1, min(x, len(lines[y - 1])), "move line-sound"); (not shift and say_content(lines[y]))
			else: clear_sel(True); play("edge text-sound", None); say_content(lines[y])

		if bf.keyPressing("down", 200):
			if suggs and y == len(lines) - 1: s_idx = (s_idx + 1) % len(suggs); bf.say(suggs[s_idx])
			elif y < len(lines) - 1: move_c(y + 1, min(x, len(lines[y + 1])), "move line-sound"); (not shift and say_content(lines[y]))
			else: clear_sel(True); play("edge text-sound", None); say_content(lines[y])

		if bf.keyPressed("home"): ny = 0 if ctrl else y; move_c(ny, 0); (not shift and say_content(lines[ny][0] if lines[ny] else "", True))
		if bf.keyPressed("end"): ny = len(lines) - 1 if ctrl else y; move_c(ny, len(lines[ny])); (not shift and say_content(lines[ny][-1] if lines[ny] else "", True))
		if bf.keyPressed("exit") or bf.keyPressed("esc"):
			if suggs: suggs.clear(); s_idx = -1; continue
			play("exit-sound", None); return None
		if bf.keyPressed("lalt") and not password: say_content("\n".join(lines))


def input(title="", text="", callback=None, password=False, get_data=True, new_config=None, window=None):
	target = window or get_window()
	if target is not None and hasattr(target, "clear_input"): target.clear_input()
	else: pygame.event.clear([pygame.KEYDOWN, pygame.KEYUP, pygame.TEXTINPUT, pygame.TEXTEDITING])
	pygame.key.start_text_input()
	pygame.key.set_text_input_rect(pygame.Rect(0, 0, 320, 32))
	try: return _input(title, text, callback, password, get_data, new_config, window)
	finally: pygame.key.stop_text_input()


class form:
	"""NVDA & Android TalkBack accessible form with Rich Controls, Table, Tree, Dialog & Auto-Submit."""
	def __init__(self, window=None, config=None):
		self.wnd = window or get_window()
		if self.wnd is None: raise RuntimeError("Create a window before a form")
		self.config = {**deepcopy(FORM_CONFIG), **deepcopy(config or {})}
		self.items, self.cursor, self._touch, self._pending_btn = [], 0, _TouchEngine(), None

	def add(self, name, kind="button", value=None, choices=None, callback=None, config=None, **kwargs):
		valid = ("button", "check", "input", "list", "radio", "combo", "tree", "dir_tree", "slider", "tab", "context", "progress", "table", "dialog", "heading", "quote", "note", "emphasis", "frame", "live")
		if kind not in valid: raise ValueError(f"Unknown control: {kind}")
		if any(it["name"] == name for it in self.items): raise ValueError(f"Duplicate control: {name}")

		cfg = {**deepcopy(self.config), **deepcopy(config or {})}
		for k in ("readonly", "multiline", "number_only", "password", "max_length", "placeholder", "tab_page", "hint", "label", "color", "bg_color", "border_color", "font", "font_size", "pos", "size", "border", "margin", "padding", "level", "auto_submit", "adjacent_submit", "suggestions", "table_read_header", "table_read_coords", "table_cell_border"):
			if k in kwargs: cfg[k] = kwargs[k]
		if not (config and "label" in config) and "label" not in kwargs and not cfg["label"]: cfg["label"] = name
		if "suggestions" in kwargs: cfg["input"]["suggestions"] = kwargs["suggestions"]

		item = {"name": name, "kind": kind, "value": value, "callback": callback, "config": cfg}

		if kind in ("list", "radio", "combo", "context"):
			from .menu import menu
			item["menu"] = menu()
			item["menu"].init(self.wnd, items=choices or [], config=cfg["menu"])
			item["menu"].cursor = max(0, min(int(value or 0), item["menu"].Len() - 1)) if item["menu"].items else 0
			item["value"] = item["menu"].cursor if item["menu"].items else 0
			if kind == "combo": item["expanded"] = False

		elif kind == "tree":
			item["nodes"] = self._normalize_tree(choices or [])
			item["flat"] = self._flatten_tree(item["nodes"])
			item["tree_cursor"] = max(0, min(int(value or 0), len(item["flat"]) - 1)) if item["flat"] else 0
			item["value"] = item["flat"][item["tree_cursor"]]["node"]["label"] if item["flat"] else None

		elif kind == "dir_tree":
			rp = str(value or choices or os.getcwd())
			inc = bool(kwargs.get("include_files", cfg.get("include_files", True)))
			item["include_files"] = inc
			item["nodes"] = self._build_dir_nodes(rp, include_files=inc, expand_root=True)
			item["flat"] = self._flatten_tree(item["nodes"])
			item["tree_cursor"] = 0
			item["value"] = item["flat"][0]["node"]["path"] if item["flat"] else rp

		elif kind in ("slider", "progress"):
			s_min, s_max = kwargs.get("min", cfg.get("min", 0)), kwargs.get("max", cfg.get("max", 100))
			s_step = kwargs.get("step", cfg.get("step", 1))
			item.update({"min": s_min, "max": s_max, "step": s_step, "page_step": kwargs.get("page_step", cfg.get("page_step", s_step * 10)), "unit": kwargs.get("unit", cfg.get("unit", "%" if kind == "progress" else ""))})
			item["value"] = max(s_min, min(s_max, s_min if value is None else value))
			item["_last_pct"] = -1

		elif kind == "tab":
			tabs = list(choices or ["Tab 1"])
			idx = max(0, min(value, len(tabs) - 1)) if isinstance(value, int) else (tabs.index(value) if isinstance(value, str) and value in tabs else 0)
			item.update({"tabs": tabs, "tab_cursor": idx, "value": tabs[idx] if tabs else None})

		elif kind == "table":
			# choices = headers list, value = 2D rows list
			hdrs = list(kwargs.get("headers", choices or []))
			rows = [list(r) for r in (value if isinstance(value, (list, tuple)) else [])]
			cols_n = max([len(hdrs)] + [len(r) for r in rows] + [1])
			for r in rows:
				while len(r) < cols_n: r.append("")
			item.update({"headers": hdrs, "rows": rows or [[""] * cols_n], "row": 0, "col": 0})
			item["value"] = (0, 0, item["rows"][0][0] if item["rows"] else "")

		elif kind == "dialog":
			item["buttons"] = list(choices or ("OK", "Cancel"))
			item["text"] = str(value or kwargs.get("text", ""))

		elif kind == "live":
			item["_last_val"] = item["value"]

		self.items.append(item)
		return item

	def notify_live(self, name_or_text, new_value=None, interrupt=True):
		"""Dynamic live region announcement (NVDA aria-live style)."""
		for it in self.items:
			if it["name"] == name_or_text:
				if new_value is not None: it["value"] = new_value
				it["_last_val"] = it["value"]
				self._sound("live", it)
				self.wnd.say(f"{it['config']['label']}: {it['value']}" if it["config"]["label"] else str(it["value"]))
				return
		self._sound("live")
		self.wnd.say(str(name_or_text))

	def update_progress(self, name, value, announce_step=10):
		"""Update progress bar dynamically and announce milestone percentages."""
		for it in self.items:
			if it["name"] == name and it["kind"] == "progress":
				it["value"] = max(it["min"], min(it["max"], value))
				pct = int(((it["value"] - it["min"]) / ((it["max"] - it["min"]) or 1)) * 100)
				if announce_step and pct // announce_step != it.get("_last_pct", -1) // announce_step:
					it["_last_pct"] = pct
					self._sound("progress", it)
					self.wnd.say(f"{pct}%")
				return

	def _find_adjacent_button(self, item):
		"""Find button immediately next to input/combo or fallback submit button."""
		if not item["config"].get("adjacent_submit", True): return None
		vis = self._visible_items()
		if item in vis:
			idx = vis.index(item)
			if idx + 1 < len(vis) and vis[idx + 1]["kind"] == "button":
				return vis[idx + 1]
		if item["config"].get("auto_submit"):
			return next((it for it in vis if it["kind"] == "button" and it["config"].get("default_submit")), None)
		return None

	def _trigger_button(self, btn_item):
		self.cursor = self.items.index(btn_item)
		self._sound("enter", btn_item)
		self.wnd.say(f"{btn_item['config']['label']} {btn_item['config']['button-text']}")
		if btn_item["callback"]: btn_item["callback"](self, btn_item)
		self._pending_btn = btn_item["name"]
		return btn_item["name"]

	def _active_tab_pages(self):
		active = {v for it in self.items if it["kind"] == "tab" and it["value"] is not None for v in (it["value"], it["tab_cursor"])}
		return active if any(it["kind"] == "tab" for it in self.items) else None

	def _visible_items(self):
		act = self._active_tab_pages()
		return self.items if act is None else [it for it in self.items if it["kind"] == "tab" or it["config"].get("tab_page") is None or it["config"].get("tab_page") in act]

	def _build_dir_nodes(self, path, include_files=True, expand_root=False):
		path = os.path.abspath(path)
		nd = {"label": os.path.basename(path) or path, "path": path, "is_dir": os.path.isdir(path), "expanded": False, "loaded": False, "children": []}
		if nd["is_dir"] and expand_root: self._load_dir_node(nd, include_files); nd["expanded"] = True
		return [nd]

	def _load_dir_node(self, node, include_files=True):
		if not node.get("is_dir") or node.get("loaded"): return
		dirs, files = [], []
		try:
			with os.scandir(node["path"]) as entries:
				for e in entries:
					if not e.name.startswith("."):
						(dirs if e.is_dir(follow_symlinks=False) else files).append(e)
			dirs.sort(key=lambda x: x.name.lower()); files.sort(key=lambda x: x.name.lower())
			node["children"] = [{"label": d.name, "path": d.path, "is_dir": True, "expanded": False, "loaded": False, "children": []} for d in dirs] + ([{"label": f.name, "path": f.path, "is_dir": False, "expanded": False, "loaded": True, "children": []} for f in files] if include_files else [])
		except PermissionError: node["children"] = []
		node["loaded"] = True

	def _normalize_tree(self, nodes):
		res = []
		for n in nodes:
			if isinstance(n, str): res.append({"label": n, "children": [], "expanded": False})
			elif isinstance(n, dict): res.append({"label": str(n.get("label", n.get("name", "item"))), "children": self._normalize_tree(n.get("children", [])), "expanded": bool(n.get("expanded", False)), "checked": n.get("checked"), "data": n.get("data")})
		return res

	def _flatten_tree(self, nodes, level=1, parent=None):
		flat, total = [], len(nodes)
		for idx, nd in enumerate(nodes):
			ent = {"node": nd, "level": level, "index": idx + 1, "total": total, "parent": parent}
			flat.append(ent)
			if nd.get("children") and nd.get("expanded", False): flat.extend(self._flatten_tree(nd["children"], level + 1, ent))
		return flat

	def allowed(self, action, item=None):
		scopes = [self.config["permissions"]] + ([item["config"]["permissions"]] if item else [])
		return all(-1 in s or action in s for s in scopes)

	def _sound(self, action, item=None):
		snd = (item["config"] if item else self.config).get(action + "-sound")
		if snd: playsingle(snd)

	def _format_tree_entry(self, item):
		if not item["flat"]: return item["config"]["blank-text"]
		ent = item["flat"][item["tree_cursor"]]
		nd, cfg = ent["node"], item["config"]
		pts = [nd["label"]]
		if nd.get("checked") is not None: pts.append(cfg["checked-text"] if nd["checked"] else cfg["unchecked-text"])
		has_sub = bool(nd.get("children")) or (item["kind"] == "dir_tree" and nd.get("is_dir") and not nd.get("loaded"))
		if has_sub:
			pts.append(cfg["expanded-text"] if nd.get("expanded", False) else cfg["collapsed-text"])
			if nd.get("loaded", True): pts.append(f"{len(nd['children'])} items")
		pts.extend([cfg["level-text"] % ent["level"], cfg["np-text"] % (ent["index"], ent["total"])])
		return ", ".join(str(p) for p in pts if p != "")

	def _format_table_cell(self, item, read_table_meta=False):
		"""NVDA-standard table cell announcement: [Table Title, RxC], [Col Header], Row X, Col Y, Content."""
		cfg = item["config"]
		r, c = item["row"], item["col"]
		rows, hdrs = item["rows"], item["headers"]
		pts = []
		if read_table_meta:
			if cfg["label"]: pts.append(cfg["label"])
			pts.append(cfg["table-text"])
			pts.append(cfg["table-size-text"] % (len(rows), len(hdrs) or (len(rows[0]) if rows else 0)))
		if cfg.get("table_read_header", True) and hdrs and c < len(hdrs): pts.append(str(hdrs[c]))
		if cfg.get("table_read_coords", True): pts.extend([cfg["row-text"] % (r + 1), cfg["col-text"] % (c + 1)])
		val = str(rows[r][c]) if (r < len(rows) and c < len(rows[r])) else ""
		pts.append(val if val != "" else cfg["blank-text"])
		return ", ".join(pts)

	def _get_input_type_tags(self, item):
		cfg, icfg = item["config"], item["config"].get("input", {})
		pms = icfg.get("permissions", INPUT_CONFIG["permissions"])
		ro = cfg.get("readonly") or icfg.get("readonly") or not self.allowed("edit", item) or (0 not in pms and -1 not in pms)
		pw = cfg.get("password") or icfg.get("password") or (not self.allowed("read", item) and not cfg.get("readonly")) or (isinstance(pms, (list, tuple, set)) and any(isinstance(x, int) for x in pms) and 2 not in pms and -1 not in pms and not cfg.get("readonly") and not icfg.get("readonly"))
		tags = ([cfg["password-text"]] if pw else []) + [cfg["input-text"]]
		if ro: tags.append(cfg["readonly-text"])
		if cfg.get("number_only") or icfg.get("number_only"): tags.append(cfg["number-text"])
		if cfg.get("multiline") or icfg.get("multiline"): tags.append(cfg["multiline-text"])
		return tags

	def read(self):
		if not self.items: return ""
		item = self.items[self.cursor]
		if not self.allowed("read", item): return ""
		cfg, k, lbl, pts = item["config"], item["kind"], item["config"]["label"], []

		if k == "input":
			if lbl: pts.append(lbl)
			pts.extend(self._get_input_type_tags(item))
			vs = str(item["value"] if item["value"] is not None else "")
			pts.append(((str(cfg["placeholder"]) + ", ") if cfg.get("placeholder") else "") + cfg["blank-text"] if vs == "" else (" ".join([cfg["star-text"]] * len(vs)) if cfg.get("password") else vs))
		elif k == "check": pts.extend([p for p in (lbl, cfg["check-text"], cfg["checked-text"] if item["value"] else cfg["unchecked-text"]) if p])
		elif k == "button": pts.extend([p for p in (lbl, cfg["button-text"]) if p])
		elif k in ("slider", "progress"):
			pts.extend([p for p in (lbl, cfg[f"{k}-text"], f"{item['value']}{item.get('unit', '')}") if p])
		elif k == "tab":
			ct = item["tabs"][item["tab_cursor"]] if item["tabs"] else cfg["blank-text"]
			pts.append(f"{ct} {cfg['tab-text']} {cfg['selected-text']}")
			if item["tabs"]: pts.append(cfg["np-text"] % (item["tab_cursor"] + 1, len(item["tabs"])))
		elif k == "list":
			pts.extend([p for p in (lbl, cfg["list-text"], item["menu"].getReadStr() if item["menu"].items else cfg["blank-text"]) if p])
		elif k == "radio":
			ct = item["menu"].getReadStr() if item["menu"].items else cfg["blank-text"]
			pts.extend([f"{lbl}: {ct}" if lbl else ct, cfg["radio-text"], cfg["checked-text"]])
			if item["menu"].items: pts.append(cfg["np-text"] % (item["menu"].cursor + 1, item["menu"].Len()))
		elif k == "combo":
			ct = item["menu"].getReadStr() if item["menu"].items else cfg["blank-text"]
			pts.extend([p for p in (lbl, cfg["combo-text"], ct, cfg["expanded-text"] if item.get("expanded") else cfg["collapsed-text"]) if p])
		elif k in ("tree", "dir_tree"):
			pts.extend([p for p in (lbl, cfg[f"{k}-text"], self._format_tree_entry(item)) if p])
		elif k == "table":
			pts.append(self._format_table_cell(item, read_table_meta=True))
		elif k == "dialog":
			pts.extend([p for p in (lbl, cfg["dialog-text"], item.get("text", "")) if p])
		elif k == "heading":
			pts.extend([cfg["heading-text"] % cfg.get("level", 1), lbl, str(item["value"] or "")])
		elif k in ("quote", "note", "emphasis", "frame", "live"):
			pts.extend([cfg[f"{k}-text"], lbl, str(item["value"] or "")])
		elif k == "context":
			pts.extend([p for p in (lbl, cfg["context-text"]) if p])

		if cfg["hint"]: pts.append(cfg["hint"])
		if cfg["readNP"]:
			vis = self._visible_items()
			pts.append(cfg["np-text"] % ((vis.index(item) + 1) if item in vis else (self.cursor + 1), len(vis)))

		text = cfg["sep-text"].join(str(p) for p in pts if p != "")
		self.wnd.say(text)
		return text

	def move(self, step):
		vis = self._visible_items()
		if vis and self.allowed("move"):
			cur_it = self.items[self.cursor]
			# Auto-collapse combo box when moving focus away
			if cur_it["kind"] == "combo" and cur_it.get("expanded"): cur_it["expanded"] = False
			if cur_it["kind"] == "table": self.wnd.say(cur_it["config"]["out-of-table-text"])
			nxt = vis[(vis.index(cur_it) + step if cur_it in vis else 0) % len(vis)]
			self.cursor = self.items.index(nxt)
			self._sound("focus", nxt)
			if nxt["kind"] == "input": self.enter()
			else: self.read()

	def mainloop(self):
		self._sound("open")
		if self.config["label"] and self.allowed("read"): self.wnd.say(self.config["label"])
		if self.items and self.items[self.cursor]["kind"] == "input": self.enter()
		else: self.read()

	def open_context_menu(self, choices=None, item=None):
		target = item or (self.items[self.cursor] if self.items else None)
		if not self.allowed("context", target): return None
		ctx_c = choices if choices is not None else (target["config"].get("context") if target else self.config.get("context"))
		if not ctx_c: return None
		from .menu import menu
		ctx = menu()
		ctx.init(self.wnd, ttl=self.config["context-text"], items=ctx_c, config=target["config"]["menu"] if target else self.config["menu"])
		self._sound("context", target)
		ctx.open()
		while True:
			self.wnd.frameUpdate()
			res = ctx.frameUpdate()
			if res == -1: self.read(); return None
			elif res is not None and res >= 0:
				sel = ctx.getString(res)
				if target and target["config"].get("context_callback"): target["config"]["context_callback"](self, target, res, sel)
				self.read(); return sel

	def enter(self):
		if not self.items: return None
		item = self.items[self.cursor]
		if not self.allowed("enter", item): return None
		k, cfg = item["kind"], item["config"]

		if k == "check":
			if not self.allowed("check", item): return None
			item["value"] = not item["value"]
			self._sound("check", item)
			self.wnd.say(cfg["checked-text"] if item["value"] else cfg["unchecked-text"])

		elif k == "input":
			ro = cfg.get("readonly") or not self.allowed("edit", item)
			step, entered = [], []
			self._sound("edit", item)
			edit = {
				**deepcopy(cfg["input"]), "tab exit": step.append, "enter_submit": lambda: entered.append(True),
				"announce_type": True, "readonly": ro, "multiline": cfg.get("multiline", False),
				"number_only": cfg.get("number_only", False), "max_length": cfg.get("max_length", 0),
				"placeholder": cfg.get("placeholder", ""), "edit-text": cfg.get("input-text", "edit"),
				"readonly-text": cfg.get("readonly-text", "read only"), "multiline-text": cfg.get("multiline-text", "multi line"),
				"password-text": cfg.get("password-text", "password"), "number-text": cfg.get("number-text", "number only"),
				"blank-text": cfg.get("blank-text", "blank"),
			}
			if not self.allowed("read", item):
				pms = edit.get("permissions", INPUT_CONFIG["permissions"])
				edit["permissions"] = [p for p in (range(15) if -1 in pms else pms) if p != 2]
			res = input(cfg["label"] if self.allowed("read", item) else "", str(item["value"] if item["value"] is not None else ""), password=cfg.get("password", False), new_config=edit, window=self.wnd)
			if res is not None and not ro: item["value"] = res
			if item["callback"]: item["callback"](self, item)
			if step: self.move(step[0]); return item["name"]
			# If Enter pressed and an adjacent button exists, auto-press it!
			if entered and res is not None:
				adj_btn = self._find_adjacent_button(item)
				if adj_btn: return self._trigger_button(adj_btn)
			self.read()

		elif k == "combo":
			# Toggle expand/collapse; when collapsing via Enter, auto-trigger adjacent button if configured
			was_exp = item.get("expanded", False)
			item["expanded"] = not was_exp
			self._sound("expand" if item["expanded"] else "collapse", item)
			self.read()
			if was_exp and not item["expanded"]:
				adj_btn = self._find_adjacent_button(item)
				if adj_btn and cfg.get("auto_submit_combo", False): return self._trigger_button(adj_btn)

		elif k in ("tree", "dir_tree"):
			if item["flat"]:
				nd = item["flat"][item["tree_cursor"]]["node"]
				if k == "dir_tree" and nd.get("is_dir") and not nd.get("loaded"): self._load_dir_node(nd, item.get("include_files", True))
				if nd.get("children"):
					nd["expanded"] = not nd.get("expanded", False)
					item["flat"] = self._flatten_tree(item["nodes"])
					item["tree_cursor"] = min(item["tree_cursor"], len(item["flat"]) - 1)
					self._sound("expand" if nd["expanded"] else "collapse", item)
					self.wnd.say(self._format_tree_entry(item))
				elif nd.get("checked") is not None:
					nd["checked"] = not nd["checked"]
					self._sound("check", item)
					self.wnd.say(self._format_tree_entry(item))
				else:
					self._sound("enter", item)
					adj_btn = self._find_adjacent_button(item)
					if adj_btn and cfg.get("auto_submit_tree", False): return self._trigger_button(adj_btn)

		elif k == "dialog":
			self._sound("dialog", item)
			ans = dialog(title=cfg["label"], text=item.get("text", ""), buttons=item["buttons"], window=self.wnd)
			item["value"] = ans
			self.read()

		elif k == "table":
			if not cfg.get("readonly", True) and self.allowed("edit", item):
				r, c = item["row"], item["col"]
				new_v = input(f"{cfg['row-text'] % (r + 1)}, {cfg['col-text'] % (c + 1)}", str(item["rows"][r][c]), window=self.wnd)
				if new_v is not None:
					item["rows"][r][c] = new_v
					item["value"] = (r, c, new_v)
				self.wnd.say(self._format_table_cell(item))
			else:
				self._sound("enter", item)
				self.wnd.say(self._format_table_cell(item))

		elif k == "context":
			res = self.open_context_menu(choices=[x[0] for x in item["menu"].items], item=item)
			if res is not None: item["value"] = res
		else:
			self._sound("enter", item)

		if item["callback"]: item["callback"](self, item)
		return item["name"]

	def _update_slider(self, item):
		if not self.allowed("move", item): return None
		d = item["step"] if (self.wnd.keyPressing("right", 160) or self.wnd.keyPressing("up", 160)) else (-item["step"] if (self.wnd.keyPressing("left", 160) or self.wnd.keyPressing("down", 160)) else (item["page_step"] if self.wnd.keyPressed("pageup") else (-item["page_step"] if self.wnd.keyPressed("pagedown") else (item["min"] - item["value"] if self.wnd.keyPressed("home") else (item["max"] - item["value"] if self.wnd.keyPressed("end") else 0)))))
		if d != 0:
			nv = max(item["min"], min(item["max"], item["value"] + d))
			nv = int(nv) if isinstance(item["step"], int) and isinstance(item["min"], int) else round(nv, 4)
			if nv != item["value"]:
				item["value"] = nv; self._sound("slider", item); self.wnd.say(f"{item['value']}{item.get('unit', '')}")
				if item["callback"]: item["callback"](self, item)
		return None

	def _update_tab(self, item):
		if not item["tabs"] or not self.allowed("move", item): return None
		st = 1 if (self.wnd.keyPressed("right") or self.wnd.keySlide("right")) else (-1 if (self.wnd.keyPressed("left") or self.wnd.keySlide("left")) else 0)
		if st != 0:
			item["tab_cursor"] = (item["tab_cursor"] + st) % len(item["tabs"])
			item["value"] = item["tabs"][item["tab_cursor"]]
			self._sound("tab", item); self.read()
			if item["callback"]: item["callback"](self, item)
		return None

	def _update_tree(self, item):
		"""Full NVDA tree navigation: Up/Down, Left/Right, Home/End, * (expand all), Backspace (parent), Type-ahead."""
		if not item["flat"] or not self.allowed("move", item): return None
		moved = False
		up = self.wnd.keyPressing("up", 190) or (hasattr(self.wnd, "keySliding") and self.wnd.keySliding("up"))
		dn = self.wnd.keyPressing("down", 190) or (hasattr(self.wnd, "keySliding") and self.wnd.keySliding("down"))
		right = self.wnd.keyPressed("right") or self.wnd.keySlide("right")
		left = self.wnd.keyPressed("left") or self.wnd.keySlide("left")

		if up and item["tree_cursor"] > 0: item["tree_cursor"] -= 1; moved = True
		elif dn and item["tree_cursor"] < len(item["flat"]) - 1: item["tree_cursor"] += 1; moved = True
		elif self.wnd.keyPressed("home"): item["tree_cursor"] = 0; moved = True
		elif self.wnd.keyPressed("end"): item["tree_cursor"] = len(item["flat"]) - 1; moved = True
		elif self.wnd.keyPressed("backspace"):
			ent = item["flat"][item["tree_cursor"]]
			if ent["parent"]:
				for i, e in enumerate(item["flat"]):
					if e["node"] is ent["parent"]["node"]: item["tree_cursor"] = i; moved = True; break
		elif right:
			ent = item["flat"][item["tree_cursor"]]
			nd = ent["node"]
			if item["kind"] == "dir_tree" and nd.get("is_dir") and not nd.get("loaded"): self._load_dir_node(nd, item.get("include_files", True))
			if nd.get("children"):
				if not nd.get("expanded", False):
					nd["expanded"] = True; item["flat"] = self._flatten_tree(item["nodes"])
					self._sound("expand", item); self.wnd.say(f"{item['config']['expanded-text']}, {len(nd['children'])} items")
				elif item["tree_cursor"] + 1 < len(item["flat"]): item["tree_cursor"] += 1; moved = True
		elif left:
			ent = item["flat"][item["tree_cursor"]]
			nd = ent["node"]
			if nd.get("children") and nd.get("expanded", False):
				nd["expanded"] = False; item["flat"] = self._flatten_tree(item["nodes"])
				self._sound("collapse", item); self.wnd.say(item["config"]["collapsed-text"])
			elif ent["parent"] is not None:
				for i, e in enumerate(item["flat"]):
					if e["node"] is ent["parent"]["node"]: item["tree_cursor"] = i; moved = True; break

		# First-letter navigation & '*' expand branch
		for ev in (self.wnd.events if hasattr(self.wnd, "events") else []):
			if ev.type == pygame.TEXTINPUT and ev.text:
				ch = ev.text.lower()
				if ch == "*":
					def _exp_all(n):
						if item["kind"] == "dir_tree" and n.get("is_dir") and not n.get("loaded"): self._load_dir_node(n, item.get("include_files", True))
						if n.get("children"):
							n["expanded"] = True
							for c in n["children"]: _exp_all(c)
					_exp_all(item["flat"][item["tree_cursor"]]["node"])
					item["flat"] = self._flatten_tree(item["nodes"])
					self._sound("expand", item); self.wnd.say(item["config"]["expanded-text"])
				elif ch.isalnum():
					n_len = len(item["flat"])
					for off in range(1, n_len + 1):
						idx = (item["tree_cursor"] + off) % n_len
						if item["flat"][idx]["node"]["label"].lower().startswith(ch):
							item["tree_cursor"] = idx; moved = True; break

		if moved:
			cn = item["flat"][item["tree_cursor"]]["node"]
			item["value"] = cn.get("path", cn["label"])
			self._sound("focus", item); self.wnd.say(self._format_tree_entry(item))

		if self.wnd.keyPressed("enter") or self.wnd.keyPressed("space") or self.wnd.tap(): return self.enter()
		return None

	def _update_table(self, item):
		"""NVDA table navigation (Arrows, Ctrl+Alt+Arrows, Home/End, Ctrl+Home/End) & touch gestures."""
		if not item["rows"] or not self.allowed("move", item): return None
		r, c = item["row"], item["col"]
		max_r, max_c = len(item["rows"]) - 1, len(item["rows"][0]) - 1
		ctrl = self.wnd.keyPressing("lcontrol") or self.wnd.keyPressing("rcontrol")
		nr, nc = r, c

		if self.wnd.keyPressing("up", 180) or self.wnd.keySlide("up"): nr = max(0, r - 1)
		elif self.wnd.keyPressing("down", 180) or self.wnd.keySlide("down"): nr = min(max_r, r + 1)
		elif self.wnd.keyPressing("left", 180) or self.wnd.keySlide("left"): nc = max(0, c - 1)
		elif self.wnd.keyPressing("right", 180) or self.wnd.keySlide("right"): nc = min(max_c, c + 1)
		elif self.wnd.keyPressed("home"):
			if ctrl: nr, nc = 0, 0
			else: nc = 0
		elif self.wnd.keyPressed("end"):
			if ctrl: nr, nc = max_r, max_c
			else: nc = max_c

		if (nr, nc) != (r, c):
			item["row"], item["col"] = nr, nc
			item["value"] = (nr, nc, item["rows"][nr][nc])
			self._sound("table", item) or self._sound("focus", item)
			self.wnd.say(self._format_table_cell(item))
		elif any(self.wnd.keyPressed(k) for k in ("up", "down", "left", "right")):
			self.wnd.say(item["config"]["edge-table-text"])

		if self.wnd.keyPressed("enter") or self.wnd.tap(): return self.enter()
		return None

	def frameUpdate(self):
		if self._pending_btn:
			res, self._pending_btn = self._pending_btn, None
			return res

		# Auto-announce live regions if their value changed externally
		for it in self.items:
			if it["kind"] == "live" and it["value"] != it.get("_last_val"):
				it["_last_val"] = it["value"]
				self._sound("live", it)
				self.wnd.say(f"{it['config']['label']}: {it['value']}" if it["config"]["label"] else str(it["value"]))

		rects = _Renderer.draw_form(self)
		shift = self.wnd.keyPressing("lshift") or self.wnd.keyPressing("rshift") or self.wnd.keyPressing("shift")
		ctrl = self.wnd.keyPressing("lcontrol") or self.wnd.keyPressing("rcontrol")

		# Handle Android-style touch gestures (tap to focus, double-tap to activate, double-tap hold for context menu)
		evs = self.wnd.events if hasattr(self.wnd, "events") else []
		for act, pos in self._touch.update(evs):
			if act == "context_hold":
				self.open_context_menu(); return None
			if act == "scroll":
				self.move(1 if pos > 0 else -1); return None
			if act in ("tap", "double_tap") and rects:
				for (t_name, tidx), tr in rects.get("tabs", {}).items():
					if tr.collidepoint(pos):
						t_it = next(x for x in self.items if x["name"] == t_name)
						t_it["tab_cursor"] = tidx; t_it["value"] = t_it["tabs"][tidx]
						self.cursor = self.items.index(t_it); self._sound("tab", t_it); self.read(); return None
				for (c_name, ci), cr in rects.get("combos", {}).items():
					if cr.collidepoint(pos):
						c_it = next(x for x in self.items if x["name"] == c_name)
						c_it["menu"].cursor = ci; c_it["value"] = ci; c_it["expanded"] = False
						self._sound("collapse", c_it); self.read()
						if c_it["callback"]: c_it["callback"](self, c_it)
						return None
				for (tr_name, ti), tr_r in rects.get("trees", {}).items():
					if tr_r.collidepoint(pos):
						tr_it = next(x for x in self.items if x["name"] == tr_name)
						self.cursor = self.items.index(tr_it)
						if tr_it["tree_cursor"] == ti or act == "double_tap": return self.enter()
						tr_it["tree_cursor"] = ti; tr_it["value"] = tr_it["flat"][ti]["node"].get("path", tr_it["flat"][ti]["node"]["label"])
						self._sound("focus", tr_it); self.wnd.say(self._format_tree_entry(tr_it)); return None
				for (tb_name, ri, ci), cr in rects.get("cells", {}).items():
					if cr.collidepoint(pos) and ri >= 0:
						tb_it = next(x for x in self.items if x["name"] == tb_name)
						self.cursor = self.items.index(tb_it); tb_it["row"], tb_it["col"] = ri, ci
						tb_it["value"] = (ri, ci, tb_it["rows"][ri][ci])
						self._sound("table", tb_it); self.wnd.say(self._format_table_cell(tb_it)); return None
				for i_name, ir in rects.get("items", {}).items():
					if ir.collidepoint(pos):
						target = next(x for x in self.items if x["name"] == i_name)
						t_idx = self.items.index(target)
						if self.cursor != t_idx:
							self.cursor = t_idx; self._sound("focus", target); self.read()
							if target["kind"] in ("button", "check", "input"): return self.enter()
						else:
							return self.enter()
						return None

		if self.wnd.keyPressed("menu") or (shift and self.wnd.keyPressed("f10")):
			self.open_context_menu(); return None

		if ctrl and self.wnd.keyPressed("tab"):
			for it in self.items:
				if it["kind"] == "tab" and it["tabs"]:
					it["tab_cursor"] = (it["tab_cursor"] + (-1 if shift else 1)) % len(it["tabs"])
					it["value"] = it["tabs"][it["tab_cursor"]]
					self._sound("tab", it)
					self.wnd.say(f"{it['value']} {it['config']['tab-text']} {it['config']['selected-text']}")
					vis = self._visible_items()
					if self.items[self.cursor] not in vis and vis: self.cursor = self.items.index(vis[0])
					return None

		# NVDA Quick Navigation Keys (H: Heading, B: Button, E: Edit, C: Combo, T: Table, Q: Quote) when not in combo/tree
		cur_it = self.items[self.cursor] if self.items else None
		if self.wnd.keyPressed("tab"): self.move(-1 if shift else 1)
		elif self.wnd.keySlide("up") and (not cur_it or cur_it["kind"] != "table"): self.move(-1)
		elif self.wnd.keySlide("down") and (not cur_it or cur_it["kind"] != "table"): self.move(1)
		elif self.wnd.keyPressed("esc") and self.allowed("cancel"):
			if cur_it and cur_it["kind"] == "combo" and cur_it.get("expanded"):
				cur_it["expanded"] = False; self._sound("collapse", cur_it); self.read(); return None
			self._sound("cancel"); return -1

		elif cur_it:
			k = cur_it["kind"]
			if k == "combo":
				if self.allowed("move", cur_it):
					alt = self.wnd.keyPressing("lalt") or self.wnd.keyPressing("ralt")
					if (alt and (self.wnd.keyPressed("down") or self.wnd.keyPressed("up"))) or self.wnd.keyPressed("f4"):
						return self.enter()
					st = 1 if (self.wnd.keyPressed("down") or self.wnd.keyPressed("right") or self.wnd.keySlide("right")) else (-1 if (self.wnd.keyPressed("up") or self.wnd.keyPressed("left") or self.wnd.keySlide("left")) else 0)
					if st != 0 and cur_it["menu"].items:
						cur_it["menu"].jumpCursor((cur_it["menu"].cursor + st) % cur_it["menu"].Len())
						cur_it["value"] = cur_it["menu"].cursor
						self.wnd.say(cur_it["menu"].getReadStr())
						if cur_it["callback"]: cur_it["callback"](self, cur_it)
						return None
					if self.wnd.keyPressed("enter") or self.wnd.keyPressed("space") or self.wnd.tap():
						return self.enter()

			elif k in ("list", "radio"):
				if self.allowed("move", cur_it):
					pms = cur_it["config"]["menu"].get("permissions", ["read", "move", "enter", "cancel", "hotkey"])
					cur_it["menu"].config["permissions"] = [a for a in ("read", "move", "enter", "cancel", "hotkey") if (-1 in pms or a in pms) and self.allowed("enter" if a == "hotkey" else a, cur_it)]
					if any(self.wnd.keySlide(d) or self.wnd.keyPressed(d) for d in ("left", "right")):
						st = 1 if (self.wnd.keySlide("right") or self.wnd.keyPressed("right")) else -1
						cur_it["menu"].jumpCursor(cur_it["menu"].cursor + st)
						if k == "radio":
							cur_it["value"] = cur_it["menu"].cursor; self._sound("check", cur_it); self.read(); return None
					res = cur_it["menu"].frameUpdate()
					if k == "radio" and cur_it["value"] != cur_it["menu"].cursor:
						cur_it["value"] = cur_it["menu"].cursor; self._sound("check", cur_it); self.read()
					else: cur_it["value"] = cur_it["menu"].cursor if cur_it["menu"].items else None
					if res is not None and res >= 0: return self.enter()

			elif k in ("tree", "dir_tree"): return self._update_tree(cur_it)
			elif k == "table": return self._update_table(cur_it)
			elif k == "slider": return self._update_slider(cur_it)
			elif k == "tab": return self._update_tab(cur_it)
			elif self.wnd.keyPressed("enter") or self.wnd.keyPressed("space") or self.wnd.tap():
				return self.enter()

		return None

	def values(self):
		return {it["name"]: it["value"] for it in self.items}

	def open(self):
		"""Run modal form loop; return clicked button name or -1 on cancel."""
		self.mainloop()
		while True:
			self.wnd.frameUpdate()
			res = self.frameUpdate()
			if res == -1 or (res is not None and any(it["name"] == res and it["kind"] == "button" for it in self.items)):
				self.wnd.wait(5)
				return res

	# --- Extended Form API & NVDA Quick-Nav / Dynamic Helpers ---

	def get(self, name, fallback=None):
		"""Get control value by name."""
		return next((it["value"] for it in self.items if it["name"] == name), fallback)

	def set(self, name, value, announce=False):
		"""Set control value dynamically; auto-triggers live/progress logic if applicable."""
		for it in self.items:
			if it["name"] == name:
				if it["kind"] == "progress": self.update_progress(name, value, announce_step=10 if announce else 0); return True
				if it["kind"] == "live": self.notify_live(name, value); return True
				it["value"] = value
				if it["kind"] in ("list", "radio", "combo") and it["menu"].items:
					it["menu"].cursor = max(0, min(int(value or 0), it["menu"].Len() - 1))
				if announce: self.wnd.say(f"{it['config']['label']}: {value}")
				return True
		return False

	def set_style(self, name, **kwargs):
		"""Update visual style (color, bg_color, border_color, font, font_size, pos, size, border, margin, padding)."""
		for it in self.items:
			if it["name"] == name:
				for k in ("color", "bg_color", "border_color", "font", "font_size", "pos", "size", "border", "margin", "padding", "level"):
					if k in kwargs: it["config"][k] = kwargs[k]
				return True
		return False

	def quick_nav(self, kind_filter, reverse=False):
		"""NVDA-style single-key quick navigation (H=heading, B=button, E=input, C=combo, T=table, Q=quote, F=frame)."""
		vis = self._visible_items()
		if not vis or not self.allowed("move"): return False
		cur_it = self.items[self.cursor]
		start = vis.index(cur_it) if cur_it in vis else 0
		step, n = (-1 if reverse else 1), len(vis)
		for i in range(1, n + 1):
			cand = vis[(start + i * step) % n]
			if cand["kind"] in (kind_filter if isinstance(kind_filter, (tuple, list)) else (kind_filter,)):
				if cur_it["kind"] == "combo" and cur_it.get("expanded"): cur_it["expanded"] = False
				self.cursor = self.items.index(cand)
				self._sound("focus", cand); self.read(); return True
		self._sound("cancel"); return False

	def set_cell(self, table_name, row, col, val, announce=False):
		"""Update a specific cell in a table control."""
		for it in self.items:
			if it["name"] == table_name and it["kind"] == "table":
				if 0 <= row < len(it["rows"]) and 0 <= col < len(it["rows"][row]):
					it["rows"][row][col] = val
					if it["row"] == row and it["col"] == col: it["value"] = (row, col, val)
					if announce: self.wnd.say(self._format_table_cell(it))
					return True
		return False

	def add_row(self, table_name, row_data, announce=False):
		"""Append a row to a table control dynamically."""
		for it in self.items:
			if it["name"] == table_name and it["kind"] == "table":
				cols_n = max(len(it["headers"]), len(it["rows"][0]) if it["rows"] else 1)
				r = list(row_data)[:cols_n] + [""] * max(0, cols_n - len(row_data))
				it["rows"].append(r)
				if announce: self.wnd.say(it["config"]["row-text"] % len(it["rows"]))
				return True
		return False

	def save_values(self, filepath):
		"""Save form values using pyaudiogaming.file if available."""
		try:
			from . import file as pfile
			return pfile.save(filepath, self.values())
		except Exception:
			return False

	def load_values(self, filepath):
		"""Load form values using pyaudiogaming.file if available."""
		try:
			from . import file as pfile
			data = pfile.load(filepath)
			if isinstance(data, dict):
				for k, v in data.items(): self.set(k, v)
				return True
		except Exception:
			pass
		return False


# --- Standalone Module-Level Shorthand Helpers ---

def get_form_config(key="", fallback=None):
	"""Get FORM_CONFIG key or copy of full config."""
	return deepcopy(FORM_CONFIG) if key == "" else FORM_CONFIG.get(key, fallback)


def set_form_config(data, fallback=None):
	"""Update global FORM_CONFIG dictionary in-place."""
	try: FORM_CONFIG.update(data); return FORM_CONFIG
	except Exception: return fallback if fallback is not None else {}


def confirm(title="Confirm", text="Are you sure?", yes_text="Yes", no_text="No", window=None):
	"""Quick Yes/No modal dialog returning True if Yes is chosen."""
	return dialog(title=title, text=text, buttons=(yes_text, no_text), default=0, cancel=1, window=window) == yes_text


def prompt_chat(title="Message", placeholder="Type a message...", send_label="Send", suggestions=None, window=None):
	"""Android-style inline Input + adjacent Send button form; pressing Enter in input auto-clicks Send."""
	f = form(window=window, config={"label": title})
	f.add("msg", "input", value="", placeholder=placeholder, suggestions=suggestions or [], adjacent_submit=True)
	f.add("send", "button", label=send_label)
	return f.get("msg") if f.open() == "send" else None