# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Accessible GUI toolkit with wx, Qt, Tkinter, and audio form backends.
# Supports Windows, Linux, macOS, Android, and iOS.

import os
import sys

from . import inputBox, system
from .utils import open_url

__all__ = [
	"Window",
	"WxWindow",
	"QtWindow",
	"TkWindow",
	"AudioWindow",
	"detect_gui_backend",
]

wx = None


def _try_import_qt():
	try:
		from PySide6 import QtWidgets, QtCore, QtGui
		return QtWidgets, QtCore, QtGui
	except ImportError:
		try:
			from PyQt6 import QtWidgets, QtCore, QtGui
			return QtWidgets, QtCore, QtGui
		except ImportError:
			return None


def _try_import_tk():
	try:
		import tkinter as tk
		from tkinter import ttk, messagebox, filedialog, simpledialog
		return tk, ttk, messagebox, filedialog, simpledialog
	except Exception:
		return None


def detect_gui_backend(preferred: str = "auto") -> str:
	"""Return the best available GUI backend name: ``'wx'``, ``'qt'``, ``'tk'``, or ``'audio'``."""
	pref = (preferred or "auto").lower().strip()
	os_name = system.get_platform()["os"]
	if pref in ("audio", "vb") or os_name in ("android", "ios", "web"):
		return "audio"

	if pref == "wx":
		return "wx" if inputBox.check() is not None else "audio"
	if pref == "qt":
		return "qt" if _try_import_qt() is not None else "audio"
	if pref == "tk":
		return "tk" if _try_import_tk() is not None else "audio"

	if os_name in ("linux", "macos"):
		if _try_import_qt() is not None:
			return "qt"
		if inputBox.check() is not None:
			return "wx"
		if _try_import_tk() is not None:
			return "tk"
		return "audio"

	if inputBox.check() is not None:
		return "wx"
	if _try_import_qt() is not None:
		return "qt"
	if _try_import_tk() is not None:
		return "tk"
	return "audio"


class _ContextGuard:
	"""Lightweight context manager for ``with w.row():``, ``with w.group(...):``, ``with w.page(...):``."""

	def __init__(self, on_exit):
		self._on_exit = on_exit

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self._on_exit:
			self._on_exit()
		return False


# ==============================================================================
# BASE INTERFACE (Shared declarative builder & convenience wrappers)
# ==============================================================================

class _BaseGuiWindow:
	backend_name = "base"

	def label(self, text, font=None, color=None):
		return self.print(text, font=font, color=color)

	def switch(self, label, value=False, handler=None, font=None, color=None):
		return self.checkbox(label, value=value, handler=handler, font=font, color=color)

	def values(self) -> dict:
		return {k: self.get(k) for k in self.elements}

	def run(self):
		return self.frameUpdate()

	def build(self, schema: list):
		"""Declaratively construct controls from a list of dicts.

		Example::

			w.build([
				{"type": "input", "label": "Username", "value": "alice"},
				{"type": "group", "label": "Audio", "items": [
					{"type": "slider", "label": "Volume", "min_val": 0, "max_val": 100, "value": 80},
					{"type": "checkbox", "label": "Mute", "value": False},
				]},
				{"type": "row", "items": [
					{"type": "button", "label": "Save", "handler": on_save},
					{"type": "button", "label": "Cancel", "handler": lambda _: w.close()},
				]},
			])
		"""
		for spec in (schema or []):
			if not isinstance(spec, dict):
				continue
			t = str(spec.get("type", "label")).lower().strip()
			opts = {k: v for k, v in spec.items() if k not in ("type", "items")}
			sub_items = spec.get("items") or []
			if t == "row":
				with self.row():
					self.build(sub_items)
			elif t == "group":
				with self.group(opts.get("label", "Group")):
					self.build(sub_items)
			elif t == "page":
				with self.page(opts.get("label") or opts.get("title", "Page")):
					self.build(sub_items)
			elif t == "separator":
				self.separator()
			elif hasattr(self, t):
				getattr(self, t)(**opts)
		return self


# ==============================================================================
# BACKEND 1: wxPython (Windows / Desktop Native)
# ==============================================================================

class WxWindow(_BaseGuiWindow):
	backend_name = "wx"

	def __init__(self, title="PyAudioGaming App", size=(500, 400)):
		global wx
		wx = inputBox.check()
		if wx is None:
			raise ImportError("wxPython is not installed")
		self.app = wx.GetApp() or wx.App(False)
		self.frame = wx.Frame(None, title=str(title), size=tuple(size))
		self.panel = wx.Panel(self.frame)
		self.elements = {}
		self._meta = {}
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer)
		self._parent_stack = [(self.panel, self.sizer)]
		self._notebook = None
		self._shortcuts = []
		self._close_cb = None

	def _cur(self):
		return self._parent_stack[-1]

	def _apply_style(self, ctrl, font=None, color=None):
		if font is not None:
			ctrl.SetFont(font)
		if color is not None:
			ctrl.SetForegroundColour(color)

	def row(self):
		parent, sizer = self._cur()
		h_sizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(h_sizer, 0, wx.EXPAND | wx.ALL, 2)
		self._parent_stack.append((parent, h_sizer))
		return _ContextGuard(lambda: self._parent_stack.pop())

	def group(self, label):
		parent, sizer = self._cur()
		box = wx.StaticBox(parent, label=str(label))
		g_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
		sizer.Add(g_sizer, 0, wx.EXPAND | wx.ALL, 5)
		self._parent_stack.append((box, g_sizer))
		return _ContextGuard(lambda: self._parent_stack.pop())

	def page(self, title):
		if self._notebook is None:
			self._notebook = wx.Notebook(self.panel)
			self.sizer.Add(self._notebook, 1, wx.EXPAND | wx.ALL, 5)
		pg = wx.Panel(self._notebook)
		pg_sizer = wx.BoxSizer(wx.VERTICAL)
		pg.SetSizer(pg_sizer)
		self._notebook.AddPage(pg, str(title))
		self._parent_stack.append((pg, pg_sizer))
		return _ContextGuard(lambda: self._parent_stack.pop())

	def button(self, label, handler=None, font=None, color=None):
		parent, sizer = self._cur()
		btn = wx.Button(parent, label=str(label))
		self._apply_style(btn, font, color)
		if handler:
			btn.Bind(wx.EVT_BUTTON, lambda evt: handler(btn))
		sizer.Add(btn, 0, wx.ALL | wx.EXPAND, 5)
		self.elements[label] = btn
		self._meta[label] = ("button", None)
		return btn

	def print(self, text, font=None, color=None):
		parent, sizer = self._cur()
		st = wx.StaticText(parent, label=str(text))
		self._apply_style(st, font, color)
		sizer.Add(st, 0, wx.ALL, 5)
		self.elements[text] = st
		self._meta[text] = ("label", None)
		return st

	def input(self, label, value="", font=None, password=False, multiline=False, placeholder="", color=None):
		parent, sizer = self._cur()
		row = wx.BoxSizer(wx.HORIZONTAL)
		st = wx.StaticText(parent, label=str(label))
		style = (wx.TE_PASSWORD if password else 0) | (wx.TE_MULTILINE if multiline else 0)
		tc = wx.TextCtrl(parent, value=str(value), style=style)
		if placeholder and hasattr(tc, "SetHint"):
			tc.SetHint(str(placeholder))
		self._apply_style(st, font, color)
		self._apply_style(tc, font, color)
		row.Add(st, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
		row.Add(tc, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(row, 1 if multiline else 0, wx.EXPAND)
		self.elements[label] = tc
		self._meta[label] = ("input", st)
		return tc

	def checkbox(self, label, value=False, handler=None, font=None, color=None):
		parent, sizer = self._cur()
		cb = wx.CheckBox(parent, label=str(label))
		cb.SetValue(bool(value))
		self._apply_style(cb, font, color)
		if handler:
			cb.Bind(wx.EVT_CHECKBOX, lambda evt: handler(cb.GetValue()))
		sizer.Add(cb, 0, wx.ALL, 5)
		self.elements[label] = cb
		self._meta[label] = ("checkbox", None)
		return cb

	def slider(self, label, min_val=0, max_val=100, value=50, step=1, handler=None, font=None, color=None):
		parent, sizer = self._cur()
		row = wx.BoxSizer(wx.HORIZONTAL)
		st = wx.StaticText(parent, label=str(label))
		sl = wx.Slider(parent, value=int(value), minValue=int(min_val), maxValue=int(max_val), style=wx.SL_HORIZONTAL | wx.SL_LABELS)
		self._apply_style(st, font, color)
		if handler:
			sl.Bind(wx.EVT_SLIDER, lambda evt: handler(sl.GetValue()))
		row.Add(st, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
		row.Add(sl, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(row, 0, wx.EXPAND)
		self.elements[label] = sl
		self._meta[label] = ("slider", st)
		return sl

	def spin(self, label, min_val=0, max_val=100, value=0, step=1, handler=None, font=None, color=None):
		parent, sizer = self._cur()
		row = wx.BoxSizer(wx.HORIZONTAL)
		st = wx.StaticText(parent, label=str(label))
		sp = wx.SpinCtrl(parent, value=str(int(value)), min=int(min_val), max=int(max_val), initial=int(value))
		self._apply_style(st, font, color)
		if handler:
			sp.Bind(wx.EVT_SPINCTRL, lambda evt: handler(sp.GetValue()))
		row.Add(st, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
		row.Add(sp, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(row, 0, wx.EXPAND)
		self.elements[label] = sp
		self._meta[label] = ("spin", st)
		return sp

	def combo(self, label, choices=(), value=0, handler=None, font=None, color=None):
		parent, sizer = self._cur()
		row = wx.BoxSizer(wx.HORIZONTAL)
		st = wx.StaticText(parent, label=str(label))
		ch_list = [str(c) for c in choices]
		cb = wx.Choice(parent, choices=ch_list)
		if ch_list:
			cb.SetSelection(max(0, min(int(value), len(ch_list) - 1)))
		self._apply_style(st, font, color)
		if handler:
			cb.Bind(wx.EVT_CHOICE, lambda evt: handler(cb.GetSelection()))
		row.Add(st, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
		row.Add(cb, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(row, 0, wx.EXPAND)
		self.elements[label] = cb
		self._meta[label] = ("combo", st)
		return cb

	def listbox(self, label, choices=(), value=0, handler=None, font=None, color=None):
		parent, sizer = self._cur()
		st = wx.StaticText(parent, label=str(label))
		ch_list = [str(c) for c in choices]
		lb = wx.ListBox(parent, choices=ch_list)
		if ch_list:
			lb.SetSelection(max(0, min(int(value), len(ch_list) - 1)))
		self._apply_style(st, font, color)
		self._apply_style(lb, font, color)
		if handler:
			lb.Bind(wx.EVT_LISTBOX, lambda evt: handler(lb.GetSelection()))
		sizer.Add(st, 0, wx.LEFT | wx.TOP, 5)
		sizer.Add(lb, 1, wx.ALL | wx.EXPAND, 5)
		self.elements[label] = lb
		self._meta[label] = ("listbox", st)
		return lb

	def radio(self, label, choices=(), value=0, handler=None, font=None, color=None):
		parent, sizer = self._cur()
		ch_list = [str(c) for c in choices] or [""]
		rb = wx.RadioBox(parent, label=str(label), choices=ch_list)
		rb.SetSelection(max(0, min(int(value), len(ch_list) - 1)))
		self._apply_style(rb, font, color)
		if handler:
			rb.Bind(wx.EVT_RADIOBOX, lambda evt: handler(rb.GetSelection()))
		sizer.Add(rb, 0, wx.ALL | wx.EXPAND, 5)
		self.elements[label] = rb
		self._meta[label] = ("radio", None)
		return rb

	def progress(self, label, value=0, max_val=100, font=None, color=None):
		parent, sizer = self._cur()
		st = wx.StaticText(parent, label=str(label))
		g = wx.Gauge(parent, range=max(1, int(max_val)))
		g.SetValue(max(0, min(int(value), int(max_val))))
		self._apply_style(st, font, color)
		sizer.Add(st, 0, wx.LEFT | wx.TOP, 5)
		sizer.Add(g, 0, wx.ALL | wx.EXPAND, 5)
		self.elements[label] = g
		self._meta[label] = ("progress", st)
		return g

	def table(self, label, headers=(), rows=(), handler=None, font=None, color=None):
		parent, sizer = self._cur()
		st = wx.StaticText(parent, label=str(label))
		lc = wx.ListCtrl(parent, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
		for ci, h in enumerate(headers):
			lc.InsertColumn(ci, str(h), width=120)
		for r in rows:
			idx = lc.InsertItem(lc.GetItemCount(), str(r[0]) if r else "")
			for ci in range(1, len(r)):
				lc.SetItem(idx, ci, str(r[ci]))
		if handler:
			lc.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda evt: handler(evt.GetIndex()))
		sizer.Add(st, 0, wx.LEFT | wx.TOP, 5)
		sizer.Add(lc, 1, wx.ALL | wx.EXPAND, 5)
		self.elements[label] = lc
		self._meta[label] = ("table", st)
		return lc

	def link(self, label, url, handler=None, font=None, color=None):
		def _on_click(btn):
			open_url(url)
			if handler:
				handler(url)
		return self.button(label, handler=_on_click, font=font, color=color)

	def separator(self):
		parent, sizer = self._cur()
		line = wx.StaticLine(parent)
		sizer.Add(line, 0, wx.ALL | wx.EXPAND, 5)
		return line

	def get(self, label, default=None):
		el = self.elements.get(label)
		if el is None:
			return default
		kind = self._meta.get(label, ("", None))[0]
		if kind in ("input", "checkbox", "slider", "spin", "progress"):
			return el.GetValue()
		if kind in ("combo", "listbox", "radio"):
			return el.GetSelection()
		if kind == "table":
			return el.GetFirstSelected()
		if kind in ("label", "button"):
			return el.GetLabel()
		return default

	def set(self, label, value):
		el = self.elements.get(label)
		if el is None:
			return False
		kind = self._meta.get(label, ("", None))[0]
		if kind == "input":
			el.SetValue(str(value))
		elif kind == "checkbox":
			el.SetValue(bool(value))
		elif kind in ("slider", "spin", "progress"):
			el.SetValue(int(value))
		elif kind in ("combo", "listbox", "radio"):
			el.SetSelection(int(value))
		elif kind in ("label", "button"):
			el.SetLabel(str(value))
		return True

	def enable(self, label, enabled=True):
		el = self.elements.get(label)
		if el is not None:
			el.Enable(bool(enabled))

	def show(self, label, visible=True):
		el = self.elements.get(label)
		meta = self._meta.get(label, (None, None))
		if el is not None:
			el.Show(bool(visible))
			if meta[1] is not None:
				meta[1].Show(bool(visible))
			self.panel.Layout()

	def focus(self, label):
		el = self.elements.get(label)
		if el is not None:
			el.SetFocus()

	def set_title(self, title):
		self.frame.SetTitle(str(title))

	def on_close(self, handler):
		self._close_cb = handler
		def _on_evt(evt):
			if self._close_cb and self._close_cb() is False:
				evt.Veto()
			else:
				evt.Skip()
		self.frame.Bind(wx.EVT_CLOSE, _on_evt)

	def after(self, ms, callback):
		return wx.CallLater(max(1, int(ms)), callback)

	def shortcut(self, combo, handler):
		parts = [p.strip().lower() for p in str(combo).split("+") if p.strip()]
		if not parts:
			return
		mods = 0
		for m in parts[:-1]:
			if m in ("ctrl", "control"):
				mods |= wx.ACCEL_CTRL
			elif m == "shift":
				mods |= wx.ACCEL_SHIFT
			elif m == "alt":
				mods |= wx.ACCEL_ALT
		k = parts[-1]
		keycode = getattr(wx, f"WXK_{k.upper()}", ord(k.upper()) if len(k) == 1 else 0)
		if keycode:
			wid = wx.NewIdRef()
			self.frame.Bind(wx.EVT_MENU, lambda evt: handler(), id=wid)
			self._shortcuts.append((mods, keycode, wid))
			self.frame.SetAcceleratorTable(wx.AcceleratorTable(self._shortcuts))

	def remove(self, label):
		el = self.elements.pop(label, None)
		meta = self._meta.pop(label, (None, None))
		if el is not None:
			if meta[1] is not None:
				meta[1].Destroy()
			el.Destroy()
			self.panel.Layout()

	def edit(self, label, font=None, color=None, text=None):
		el = self.elements.get(label)
		if el is None:
			return None
		self._apply_style(el, font, color)
		if text is not None and hasattr(el, "SetLabel"):
			el.SetLabel(str(text))
		return el

	def alert(self, title, text, level="info"):
		flags = {"info": wx.ICON_INFORMATION, "warning": wx.ICON_WARNING, "error": wx.ICON_ERROR}.get(level, wx.ICON_INFORMATION)
		wx.MessageBox(str(text), str(title), wx.OK | flags, self.frame)

	def confirm(self, title, text) -> bool:
		return wx.MessageBox(str(text), str(title), wx.YES_NO | wx.ICON_QUESTION, self.frame) == wx.YES

	def prompt(self, title, text="", default=""):
		dlg = wx.TextEntryDialog(self.frame, str(text), str(title), value=str(default))
		try:
			return dlg.GetValue() if dlg.ShowModal() == wx.ID_OK else None
		finally:
			dlg.Destroy()

	def open_file(self, title="Open File", wildcard="All files (*.*)|*.*"):
		dlg = wx.FileDialog(self.frame, str(title), wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		try:
			return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else None
		finally:
			dlg.Destroy()

	def save_file(self, title="Save File", wildcard="All files (*.*)|*.*"):
		dlg = wx.FileDialog(self.frame, str(title), wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
		try:
			return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else None
		finally:
			dlg.Destroy()

	def open_folder(self, title="Select Folder"):
		dlg = wx.DirDialog(self.frame, str(title))
		try:
			return dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else None
		finally:
			dlg.Destroy()

	def close(self):
		self.frame.Close()

	def frameUpdate(self):
		self.panel.Layout()
		self.frame.Show()
		self.app.MainLoop()


# ==============================================================================
# BACKEND 2: Qt (PySide6 / PyQt6 — Linux, macOS, Windows)
# ==============================================================================

class QtWindow(_BaseGuiWindow):
	backend_name = "qt"

	def __init__(self, title="PyAudioGaming App", size=(500, 400)):
		mods = _try_import_qt()
		if mods is None:
			raise ImportError("Neither PySide6 nor PyQt6 is installed")
		self.qt, self.qt_core, self.qt_gui = mods
		self.app = self.qt.QApplication.instance() or self.qt.QApplication([])
		self.frame = self.qt.QWidget()
		self.frame.setWindowTitle(str(title))
		self.frame.resize(*size)
		self.layout = self.qt.QVBoxLayout(self.frame)
		self._layout_stack = [self.layout]
		self._tabs = None
		self.elements = {}
		self._meta = {}
		self._shortcuts = []

	def _cur_layout(self):
		return self._layout_stack[-1]

	def row(self):
		hl = self.qt.QHBoxLayout()
		self._cur_layout().addLayout(hl)
		self._layout_stack.append(hl)
		return _ContextGuard(lambda: self._layout_stack.pop())

	def group(self, label):
		box = self.qt.QGroupBox(str(label))
		vl = self.qt.QVBoxLayout(box)
		self._cur_layout().addWidget(box)
		self._layout_stack.append(vl)
		return _ContextGuard(lambda: self._layout_stack.pop())

	def page(self, title):
		if self._tabs is None:
			self._tabs = self.qt.QTabWidget()
			self.layout.addWidget(self._tabs)
		pg = self.qt.QWidget()
		vl = self.qt.QVBoxLayout(pg)
		self._tabs.addTab(pg, str(title))
		self._layout_stack.append(vl)
		return _ContextGuard(lambda: self._layout_stack.pop())

	def _add(self, label, widget, kind, font=None, color=None, caption=None):
		widget.setAccessibleName(str(label))
		if font is not None:
			widget.setFont(font)
		if color is not None:
			palette = widget.palette()
			qcol = self.qt_gui.QColor(color)
			palette.setColor(self.qt_gui.QPalette.ColorRole.WindowText, qcol)
			palette.setColor(self.qt_gui.QPalette.ColorRole.Text, qcol)
			widget.setPalette(palette)
		self._cur_layout().addWidget(widget)
		self.elements[label] = widget
		self._meta[label] = (kind, caption)
		return widget

	def button(self, label, handler=None, font=None, color=None):
		w = self._add(label, self.qt.QPushButton(str(label)), "button", font, color)
		if handler:
			w.clicked.connect(lambda checked=False: handler(w))
		return w

	def print(self, text, font=None, color=None):
		return self._add(text, self.qt.QLabel(str(text)), "label", font, color)

	def input(self, label, value="", font=None, password=False, multiline=False, placeholder="", color=None):
		cap = self.qt.QLabel(str(label))
		self._cur_layout().addWidget(cap)
		if multiline:
			w = self.qt.QPlainTextEdit(str(value))
			if placeholder:
				w.setPlaceholderText(str(placeholder))
			kind = "multiline"
		else:
			w = self.qt.QLineEdit(str(value))
			if password:
				w.setEchoMode(self.qt.QLineEdit.EchoMode.Password)
			if placeholder:
				w.setPlaceholderText(str(placeholder))
			kind = "input"
		cap.setBuddy(w)
		return self._add(label, w, kind, font, color, caption=cap)

	def checkbox(self, label, value=False, handler=None, font=None, color=None):
		w = self.qt.QCheckBox(str(label))
		w.setChecked(bool(value))
		if handler:
			w.toggled.connect(lambda checked: handler(bool(checked)))
		return self._add(label, w, "checkbox", font, color)

	def slider(self, label, min_val=0, max_val=100, value=50, step=1, handler=None, font=None, color=None):
		cap = self.qt.QLabel(str(label))
		self._cur_layout().addWidget(cap)
		w = self.qt.QSlider(self.qt_core.Qt.Orientation.Horizontal)
		w.setRange(int(min_val), int(max_val))
		w.setSingleStep(max(1, int(step)))
		w.setValue(int(value))
		cap.setBuddy(w)
		if handler:
			w.valueChanged.connect(lambda v: handler(int(v)))
		return self._add(label, w, "slider", font, color, caption=cap)

	def spin(self, label, min_val=0, max_val=100, value=0, step=1, handler=None, font=None, color=None):
		cap = self.qt.QLabel(str(label))
		self._cur_layout().addWidget(cap)
		w = self.qt.QSpinBox()
		w.setRange(int(min_val), int(max_val))
		w.setSingleStep(max(1, int(step)))
		w.setValue(int(value))
		cap.setBuddy(w)
		if handler:
			w.valueChanged.connect(lambda v: handler(int(v)))
		return self._add(label, w, "spin", font, color, caption=cap)

	def combo(self, label, choices=(), value=0, handler=None, font=None, color=None):
		cap = self.qt.QLabel(str(label))
		self._cur_layout().addWidget(cap)
		w = self.qt.QComboBox()
		w.addItems([str(c) for c in choices])
		if choices:
			w.setCurrentIndex(max(0, min(int(value), len(choices) - 1)))
		cap.setBuddy(w)
		if handler:
			w.currentIndexChanged.connect(lambda idx: handler(int(idx)))
		return self._add(label, w, "combo", font, color, caption=cap)

	def listbox(self, label, choices=(), value=0, handler=None, font=None, color=None):
		cap = self.qt.QLabel(str(label))
		self._cur_layout().addWidget(cap)
		w = self.qt.QListWidget()
		w.addItems([str(c) for c in choices])
		if choices:
			w.setCurrentRow(max(0, min(int(value), len(choices) - 1)))
		cap.setBuddy(w)
		if handler:
			w.currentRowChanged.connect(lambda r: handler(int(r)))
		return self._add(label, w, "listbox", font, color, caption=cap)

	def radio(self, label, choices=(), value=0, handler=None, font=None, color=None):
		box = self.qt.QGroupBox(str(label))
		vbox = self.qt.QVBoxLayout(box)
		group = self.qt.QButtonGroup(box)
		for idx, ch in enumerate(choices):
			rb = self.qt.QRadioButton(str(ch))
			if idx == int(value):
				rb.setChecked(True)
			group.addButton(rb, idx)
			vbox.addWidget(rb)
		if handler:
			group.idClicked.connect(lambda idx: handler(int(idx)))
		box._group = group
		return self._add(label, box, "radio", font, color)

	def progress(self, label, value=0, max_val=100, font=None, color=None):
		cap = self.qt.QLabel(str(label))
		self._cur_layout().addWidget(cap)
		w = self.qt.QProgressBar()
		w.setRange(0, max(1, int(max_val)))
		w.setValue(int(value))
		return self._add(label, w, "progress", font, color, caption=cap)

	def table(self, label, headers=(), rows=(), handler=None, font=None, color=None):
		cap = self.qt.QLabel(str(label))
		self._cur_layout().addWidget(cap)
		w = self.qt.QTableWidget(len(rows), len(headers))
		w.setHorizontalHeaderLabels([str(h) for h in headers])
		for ri, r in enumerate(rows):
			for ci, val in enumerate(r):
				w.setItem(ri, ci, self.qt.QTableWidgetItem(str(val)))
		if handler:
			w.cellClicked.connect(lambda r, c: handler((r, c)))
		return self._add(label, w, "table", font, color, caption=cap)

	def link(self, label, url, handler=None, font=None, color=None):
		def _on_click(w):
			open_url(url)
			if handler:
				handler(url)
		return self.button(label, handler=_on_click, font=font, color=color)

	def separator(self):
		line = self.qt.QFrame()
		line.setFrameShape(self.qt.QFrame.Shape.HLine)
		self._cur_layout().addWidget(line)
		return line

	def get(self, label, default=None):
		w = self.elements.get(label)
		if w is None:
			return default
		kind = self._meta.get(label, ("", None))[0]
		if kind == "input":
			return w.text()
		if kind == "multiline":
			return w.toPlainText()
		if kind == "checkbox":
			return w.isChecked()
		if kind in ("slider", "spin", "progress"):
			return w.value()
		if kind == "combo":
			return w.currentIndex()
		if kind == "listbox":
			return w.currentRow()
		if kind == "radio":
			return w._group.checkedId()
		if kind == "table":
			return w.currentRow()
		if kind in ("label", "button"):
			return w.text()
		return default

	def set(self, label, value):
		w = self.elements.get(label)
		if w is None:
			return False
		kind = self._meta.get(label, ("", None))[0]
		if kind == "input":
			w.setText(str(value))
		elif kind == "multiline":
			w.setPlainText(str(value))
		elif kind == "checkbox":
			w.setChecked(bool(value))
		elif kind in ("slider", "spin", "progress"):
			w.setValue(int(value))
		elif kind == "combo":
			w.setCurrentIndex(int(value))
		elif kind == "listbox":
			w.setCurrentRow(int(value))
		elif kind == "radio":
			btn = w._group.button(int(value))
			if btn:
				btn.setChecked(True)
		elif kind in ("label", "button"):
			w.setText(str(value))
		return True

	def enable(self, label, enabled=True):
		w = self.elements.get(label)
		if w is not None:
			w.setEnabled(bool(enabled))

	def show(self, label, visible=True):
		w = self.elements.get(label)
		meta = self._meta.get(label, (None, None))
		if w is not None:
			w.setVisible(bool(visible))
			if meta[1] is not None:
				meta[1].setVisible(bool(visible))

	def focus(self, label):
		w = self.elements.get(label)
		if w is not None:
			w.setFocus()

	def set_title(self, title):
		self.frame.setWindowTitle(str(title))

	def on_close(self, handler):
		orig = self.frame.closeEvent
		def _wrapped(evt):
			if handler() is False:
				evt.ignore()
			else:
				orig(evt)
		self.frame.closeEvent = _wrapped

	def after(self, ms, callback):
		self.qt_core.QTimer.singleShot(max(1, int(ms)), callback)

	def shortcut(self, combo, handler):
		sc = self.qt_gui.QShortcut(self.qt_gui.QKeySequence(str(combo)), self.frame)
		sc.activated.connect(handler)
		self._shortcuts.append(sc)

	def remove(self, label):
		w = self.elements.pop(label, None)
		meta = self._meta.pop(label, (None, None))
		if w is not None:
			if meta[1] is not None:
				meta[1].deleteLater()
			w.deleteLater()

	def edit(self, label, font=None, color=None, text=None):
		w = self.elements.get(label)
		if w is None:
			return None
		if font is not None:
			w.setFont(font)
		if color is not None:
			palette = w.palette()
			qcol = self.qt_gui.QColor(color)
			palette.setColor(self.qt_gui.QPalette.ColorRole.WindowText, qcol)
			palette.setColor(self.qt_gui.QPalette.ColorRole.Text, qcol)
			w.setPalette(palette)
		if text is not None and hasattr(w, "setText"):
			w.setText(str(text))
		return w

	def alert(self, title, text, level="info"):
		fn = {"warning": self.qt.QMessageBox.warning, "error": self.qt.QMessageBox.critical}.get(level, self.qt.QMessageBox.information)
		fn(self.frame, str(title), str(text))

	def confirm(self, title, text) -> bool:
		return self.qt.QMessageBox.question(self.frame, str(title), str(text)) == self.qt.QMessageBox.StandardButton.Yes

	def prompt(self, title, text="", default=""):
		val, ok = self.qt.QInputDialog.getText(self.frame, str(title), str(text), text=str(default))
		return val if ok else None

	def open_file(self, title="Open File", wildcard="All Files (*.*)"):
		path, _ = self.qt.QFileDialog.getOpenFileName(self.frame, str(title), "", wildcard)
		return path or None

	def save_file(self, title="Save File", wildcard="All Files (*.*)"):
		path, _ = self.qt.QFileDialog.getSaveFileName(self.frame, str(title), "", wildcard)
		return path or None

	def open_folder(self, title="Select Folder"):
		path = self.qt.QFileDialog.getExistingDirectory(self.frame, str(title))
		return path or None

	def close(self):
		self.frame.close()

	def frameUpdate(self):
		self.frame.show()
		return self.app.exec()


# ==============================================================================
# BACKEND 3: Tkinter (Stdlib Desktop Zero-Dependency Fallback)
# ==============================================================================

class TkWindow(_BaseGuiWindow):
	backend_name = "tk"

	def __init__(self, title="PyAudioGaming App", size=(500, 400)):
		mods = _try_import_tk()
		if mods is None:
			raise ImportError("tkinter is not available")
		self.tk, self.ttk, self.messagebox, self.filedialog, self.simpledialog = mods
		self.frame = self.tk.Tk()
		self.frame.title(str(title))
		self.frame.geometry(f"{int(size[0])}x{int(size[1])}")
		self._parent_stack = [(self.frame, "vertical")]
		self._notebook = None
		self.elements = {}
		self._vars = {}
		self._meta = {}

	def _cur(self):
		return self._parent_stack[-1]

	def _pack(self, widget, fill="x", expand=False, padx=8, pady=4):
		_, orient = self._cur()
		if orient == "horizontal":
			widget.pack(side="left", fill="x", expand=True, padx=4, pady=pady)
		else:
			widget.pack(fill=fill, expand=expand, padx=padx, pady=pady)

	def row(self):
		parent, _ = self._cur()
		rf = self.tk.Frame(parent)
		self._pack(rf, fill="x", pady=2)
		self._parent_stack.append((rf, "horizontal"))
		return _ContextGuard(lambda: self._parent_stack.pop())

	def group(self, label):
		parent, _ = self._cur()
		gf = self.tk.LabelFrame(parent, text=str(label))
		self._pack(gf, fill="x", pady=5)
		self._parent_stack.append((gf, "vertical"))
		return _ContextGuard(lambda: self._parent_stack.pop())

	def page(self, title):
		if self._notebook is None:
			self._notebook = self.ttk.Notebook(self.frame)
			self._notebook.pack(fill="both", expand=True, padx=6, pady=6)
		pg = self.tk.Frame(self._notebook)
		self._notebook.add(pg, text=str(title))
		self._parent_stack.append((pg, "vertical"))
		return _ContextGuard(lambda: self._parent_stack.pop())

	def button(self, label, handler=None, font=None, color=None):
		parent, _ = self._cur()
		w = self.tk.Button(parent, text=str(label), command=(lambda: handler(w)) if handler else None)
		if font: w.config(font=font)
		if color: w.config(fg=color)
		self._pack(w)
		self.elements[label] = w
		self._meta[label] = ("button", None)
		return w

	def print(self, text, font=None, color=None):
		parent, _ = self._cur()
		w = self.tk.Label(parent, text=str(text), anchor="w")
		if font: w.config(font=font)
		if color: w.config(fg=color)
		self._pack(w)
		self.elements[text] = w
		self._meta[text] = ("label", None)
		return w

	def input(self, label, value="", font=None, password=False, multiline=False, placeholder="", color=None):
		parent, _ = self._cur()
		cap = self.tk.Label(parent, text=str(label), anchor="w")
		self._pack(cap, pady=(4, 0))
		if multiline:
			w = self.tk.Text(parent, height=4)
			w.insert("1.0", str(value))
			kind = "multiline"
		else:
			var = self.tk.StringVar(value=str(value))
			w = self.tk.Entry(parent, textvariable=var, show="*" if password else "")
			self._vars[label] = var
			kind = "input"
		if font: w.config(font=font)
		if color: w.config(fg=color)
		self._pack(w, pady=(0, 4))
		self.elements[label] = w
		self._meta[label] = (kind, cap)
		return w

	def checkbox(self, label, value=False, handler=None, font=None, color=None):
		parent, _ = self._cur()
		var = self.tk.BooleanVar(value=bool(value))
		w = self.tk.Checkbutton(parent, text=str(label), variable=var, anchor="w", command=(lambda: handler(var.get())) if handler else None)
		if font: w.config(font=font)
		if color: w.config(fg=color)
		self._pack(w)
		self.elements[label] = w
		self._vars[label] = var
		self._meta[label] = ("checkbox", None)
		return w

	def slider(self, label, min_val=0, max_val=100, value=50, step=1, handler=None, font=None, color=None):
		parent, _ = self._cur()
		var = self.tk.IntVar(value=int(value))
		w = self.tk.Scale(parent, label=str(label), from_=int(min_val), to=int(max_val), resolution=max(1, int(step)), orient="horizontal", variable=var, command=(lambda v: handler(int(float(v)))) if handler else None)
		self._pack(w)
		self.elements[label] = w
		self._vars[label] = var
		self._meta[label] = ("slider", None)
		return w

	def spin(self, label, min_val=0, max_val=100, value=0, step=1, handler=None, font=None, color=None):
		parent, _ = self._cur()
		cap = self.tk.Label(parent, text=str(label), anchor="w")
		self._pack(cap, pady=(4, 0))
		var = self.tk.IntVar(value=int(value))
		w = self.ttk.Spinbox(parent, from_=int(min_val), to=int(max_val), increment=max(1, int(step)), textvariable=var, command=(lambda: handler(var.get())) if handler else None)
		self._pack(w, pady=(0, 4))
		self.elements[label] = w
		self._vars[label] = var
		self._meta[label] = ("spin", cap)
		return w

	def combo(self, label, choices=(), value=0, handler=None, font=None, color=None):
		parent, _ = self._cur()
		cap = self.tk.Label(parent, text=str(label), anchor="w")
		self._pack(cap, pady=(4, 0))
		ch_list = [str(c) for c in choices]
		w = self.ttk.Combobox(parent, values=ch_list, state="readonly")
		if ch_list:
			w.current(max(0, min(int(value), len(ch_list) - 1)))
		if handler:
			w.bind("<<ComboboxSelected>>", lambda e: handler(w.current()))
		self._pack(w, pady=(0, 4))
		self.elements[label] = w
		self._meta[label] = ("combo", cap)
		return w

	def listbox(self, label, choices=(), value=0, handler=None, font=None, color=None):
		parent, _ = self._cur()
		cap = self.tk.Label(parent, text=str(label), anchor="w")
		self._pack(cap, pady=(4, 0))
		w = self.tk.Listbox(parent, height=min(6, max(3, len(choices))))
		for c in choices:
			w.insert("end", str(c))
		if choices:
			w.selection_set(max(0, min(int(value), len(choices) - 1)))
		if handler:
			w.bind("<<ListboxSelect>>", lambda e: handler(w.curselection()[0]) if w.curselection() else None)
		self._pack(w, fill="both", expand=True, pady=(0, 4))
		self.elements[label] = w
		self._meta[label] = ("listbox", cap)
		return w

	def radio(self, label, choices=(), value=0, handler=None, font=None, color=None):
		parent, _ = self._cur()
		grp = self.tk.LabelFrame(parent, text=str(label))
		var = self.tk.IntVar(value=int(value))
		for idx, c in enumerate(choices):
			rb = self.tk.Radiobutton(grp, text=str(c), variable=var, value=idx, anchor="w", command=(lambda i=idx: handler(i)) if handler else None)
			rb.pack(fill="x", padx=6, pady=2)
		self._pack(grp)
		self.elements[label] = grp
		self._vars[label] = var
		self._meta[label] = ("radio", None)
		return grp

	def progress(self, label, value=0, max_val=100, font=None, color=None):
		parent, _ = self._cur()
		cap = self.tk.Label(parent, text=str(label), anchor="w")
		self._pack(cap, pady=(4, 0))
		w = self.ttk.Progressbar(parent, maximum=max(1, int(max_val)), value=int(value))
		self._pack(w, pady=(0, 4))
		self.elements[label] = w
		self._meta[label] = ("progress", cap)
		return w

	def table(self, label, headers=(), rows=(), handler=None, font=None, color=None):
		parent, _ = self._cur()
		cap = self.tk.Label(parent, text=str(label), anchor="w")
		self._pack(cap, pady=(4, 0))
		cols = [str(h) for h in headers]
		w = self.ttk.Treeview(parent, columns=cols, show="headings", height=min(6, max(3, len(rows))))
		for c in cols:
			w.heading(c, text=c)
			w.column(c, width=100)
		for idx, r in enumerate(rows):
			w.insert("", "end", iid=str(idx), values=[str(x) for x in r])
		if handler:
			w.bind("<<TreeviewSelect>>", lambda e: handler(int(w.selection()[0])) if w.selection() else None)
		self._pack(w, fill="both", expand=True, pady=(0, 4))
		self.elements[label] = w
		self._meta[label] = ("table", cap)
		return w

	def link(self, label, url, handler=None, font=None, color=None):
		def _on_click(w):
			open_url(url)
			if handler:
				handler(url)
		return self.button(label, handler=_on_click, font=font, color=color or "blue")

	def separator(self):
		parent, _ = self._cur()
		sep = self.ttk.Separator(parent, orient="horizontal")
		self._pack(sep, pady=6)
		return sep

	def get(self, label, default=None):
		w = self.elements.get(label)
		if w is None:
			return default
		kind = self._meta.get(label, ("", None))[0]
		if kind in ("input", "checkbox", "slider", "spin", "radio"):
			return self._vars[label].get()
		if kind == "multiline":
			return w.get("1.0", "end-1c")
		if kind == "combo":
			return w.current()
		if kind == "listbox":
			sel = w.curselection()
			return sel[0] if sel else -1
		if kind == "table":
			sel = w.selection()
			return int(sel[0]) if sel else -1
		if kind == "progress":
			return w["value"]
		if kind in ("label", "button"):
			return w.cget("text")
		return default

	def set(self, label, value):
		w = self.elements.get(label)
		if w is None:
			return False
		kind = self._meta.get(label, ("", None))[0]
		if kind in ("input", "checkbox", "slider", "spin", "radio"):
			self._vars[label].set(value)
		elif kind == "multiline":
			w.delete("1.0", "end")
			w.insert("1.0", str(value))
		elif kind == "combo":
			w.current(int(value))
		elif kind == "listbox":
			w.selection_clear(0, "end")
			w.selection_set(int(value))
		elif kind == "progress":
			w["value"] = int(value)
		elif kind in ("label", "button"):
			w.config(text=str(value))
		return True

	def enable(self, label, enabled=True):
		w = self.elements.get(label)
		if w is not None:
			try:
				w.config(state="normal" if enabled else "disabled")
			except Exception:
				pass

	def show(self, label, visible=True):
		w = self.elements.get(label)
		meta = self._meta.get(label, (None, None))
		if w is not None:
			if visible:
				if meta[1] is not None:
					meta[1].pack(fill="x", padx=8, pady=(4, 0))
				w.pack(fill="x", padx=8, pady=4)
			else:
				w.pack_forget()
				if meta[1] is not None:
					meta[1].pack_forget()

	def focus(self, label):
		w = self.elements.get(label)
		if w is not None:
			w.focus_set()

	def set_title(self, title):
		self.frame.title(str(title))

	def on_close(self, handler):
		def _on_del():
			if handler() is not False:
				self.frame.destroy()
		self.frame.protocol("WM_DELETE_WINDOW", _on_del)

	def after(self, ms, callback):
		return self.frame.after(max(1, int(ms)), callback)

	def shortcut(self, combo, handler):
		parts = [p.strip().lower() for p in str(combo).split("+") if p.strip()]
		if not parts:
			return
		mod_map = {"ctrl": "Control", "control": "Control", "shift": "Shift", "alt": "Alt"}
		tk_parts = [mod_map.get(p, p) for p in parts[:-1]] + [parts[-1]]
		seq = "<" + "-".join(tk_parts) + ">"
		self.frame.bind_all(seq, lambda e: handler())

	def remove(self, label):
		w = self.elements.pop(label, None)
		self._vars.pop(label, None)
		meta = self._meta.pop(label, (None, None))
		if w is not None:
			if meta[1] is not None:
				meta[1].destroy()
			w.destroy()

	def edit(self, label, font=None, color=None, text=None):
		w = self.elements.get(label)
		if w is None:
			return None
		if font: w.config(font=font)
		if color: w.config(fg=color)
		if text is not None: w.config(text=str(text))
		return w

	def alert(self, title, text, level="info"):
		fn = {"warning": self.messagebox.showwarning, "error": self.messagebox.showerror}.get(level, self.messagebox.showinfo)
		fn(str(title), str(text))

	def confirm(self, title, text) -> bool:
		return bool(self.messagebox.askyesno(str(title), str(text)))

	def prompt(self, title, text="", default=""):
		return self.simpledialog.askstring(str(title), str(text), initialvalue=str(default), parent=self.frame)

	def open_file(self, title="Open File", wildcard=None):
		return self.filedialog.askopenfilename(title=str(title), parent=self.frame) or None

	def save_file(self, title="Save File", wildcard=None):
		return self.filedialog.asksaveasfilename(title=str(title), parent=self.frame) or None

	def open_folder(self, title="Select Folder"):
		return self.filedialog.askdirectory(title=str(title), parent=self.frame) or None

	def close(self):
		self.frame.destroy()

	def frameUpdate(self):
		self.frame.mainloop()


# ==============================================================================
# BACKEND 4: AudioWindow (vb.form — Android, iOS, Web, Pygame/SDL2 Accessible)
# ==============================================================================

class AudioWindow(_BaseGuiWindow):
	"""Accessible virtual GUI powered by ``vb.form`` — runs everywhere (Android, iOS, Web, PC)."""
	backend_name = "audio"

	def __init__(self, title="PyAudioGaming App", size=(500, 400), window=None):
		from . import vb
		from .timer import TimerScheduler
		from .utils import get_window
		self._vb = vb
		wnd = window or get_window()
		if wnd is None:
			raise RuntimeError("Initialize window.Window before using AudioWindow GUI controls")
		self.form = vb.form(window=wnd, config={"label": str(title)})
		self.elements = {}
		self._tab_item = None
		self._active_page = None
		self._in_row = False
		self._scheduler = TimerScheduler()
		self._shortcuts = []
		self._close_cb = None

	def _common_kwargs(self, extra=None):
		kw = {}
		if self._active_page is not None:
			kw["tab_page"] = self._active_page
		if self._in_row:
			kw["adjacent_submit"] = True
		if extra:
			kw.update(extra)
		return kw

	def row(self):
		prev = self._in_row
		self._in_row = True
		def _exit():
			self._in_row = prev
		return _ContextGuard(_exit)

	def group(self, label):
		self.form.begin_group(str(label))
		return _ContextGuard(lambda: self.form.end_group())

	def page(self, title):
		title = str(title)
		if self._tab_item is None:
			self._tab_item = self.form.add("_tabs", "tab", choices=[title], label="Pages")
		elif title not in self._tab_item["tabs"]:
			self._tab_item["tabs"].append(title)
		prev_page = self._active_page
		self._active_page = title
		def _exit():
			self._active_page = prev_page
		return _ContextGuard(_exit)

	def button(self, label, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(it)) if handler else None
		item = self.form.add(label, "button", callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def print(self, text, font=None, color=None):
		key = f"_lbl_{len(self.elements)}" if text in self.elements else text
		item = self.form.add(key, "note", value=str(text), label=str(text), font=font, color=color, **self._common_kwargs())
		self.elements[text] = item
		return item

	def input(self, label, value="", font=None, password=False, multiline=False, placeholder="", color=None):
		item = self.form.add(
			label, "input", value=str(value), label=label, password=password,
			multiline=multiline, placeholder=placeholder, font=font, color=color,
			**self._common_kwargs(),
		)
		self.elements[label] = item
		return item

	def checkbox(self, label, value=False, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(bool(it["value"]))) if handler else None
		item = self.form.add(label, "check", value=bool(value), callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def switch(self, label, value=False, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(bool(it["value"]))) if handler else None
		item = self.form.add(label, "switch", value=bool(value), callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def slider(self, label, min_val=0, max_val=100, value=50, step=1, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(it["value"])) if handler else None
		item = self.form.add(
			label, "slider", value=value, min_val=min_val, max_val=max_val, step=step,
			callback=cb, label=label, font=font, color=color, **self._common_kwargs(),
		)
		self.elements[label] = item
		return item

	def spin(self, label, min_val=0, max_val=100, value=0, step=1, handler=None, font=None, color=None):
		return self.slider(label, min_val=min_val, max_val=max_val, value=value, step=step, handler=handler, font=font, color=color)

	def combo(self, label, choices=(), value=0, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(it["value"])) if handler else None
		item = self.form.add(label, "combo", value=int(value), choices=list(choices), callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def listbox(self, label, choices=(), value=0, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(it["value"])) if handler else None
		item = self.form.add(label, "list", value=int(value), choices=list(choices), callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def radio(self, label, choices=(), value=0, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(it["value"])) if handler else None
		item = self.form.add(label, "radio", value=int(value), choices=list(choices), callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def progress(self, label, value=0, max_val=100, font=None, color=None):
		item = self.form.add(label, "progress", value=int(value), max_val=int(max_val), label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def table(self, label, headers=(), rows=(), handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(it.get("row", 0))) if handler else None
		item = self.form.add(label, "table", headers=list(headers), rows=[list(r) for r in rows], callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def link(self, label, url, handler=None, font=None, color=None):
		cb = (lambda frm, it: handler(url)) if handler else None
		item = self.form.add(label, "link", url=str(url), callback=cb, label=label, font=font, color=color, **self._common_kwargs())
		self.elements[label] = item
		return item

	def separator(self):
		return self.form.add(f"_sep_{len(self.form.items)}", "separator", **self._common_kwargs())

	def get(self, label, default=None):
		return self.form.get(label, default)

	def set(self, label, value):
		return self.form.set(label, value)

	def enable(self, label, enabled=True):
		it = self.elements.get(label)
		if it is not None:
			it["config"]["disabled"] = not bool(enabled)

	def show(self, label, visible=True):
		it = self.elements.get(label)
		if it is not None:
			it["config"]["hidden"] = not bool(visible)

	def focus(self, label):
		it = self.elements.get(label)
		if it is not None and it in self.form.items:
			self.form.cursor = self.form.items.index(it)
			self.form.read()

	def set_title(self, title):
		self.form.config["label"] = str(title)

	def on_close(self, handler):
		self._close_cb = handler

	def after(self, ms, callback):
		return self._scheduler.after(ms, callback)

	def shortcut(self, combo, handler):
		from .input_map import InputMap
		im = InputMap({"_sc": [str(combo)]})
		self._shortcuts.append((im, handler))

	def remove(self, label):
		item = self.elements.pop(label, None)
		if item and item in self.form.items:
			self.form.items.remove(item)
		self.form.cursor = max(0, min(self.form.cursor, len(self.form.items) - 1))

	def edit(self, label, font=None, color=None, text=None):
		kwargs = {}
		if font is not None: kwargs["font"] = font
		if color is not None: kwargs["color"] = color
		if text is not None: kwargs["label"] = str(text)
		if kwargs:
			self.form.set_style(label, **kwargs)
		return self.elements.get(label)

	def alert(self, title, text, level="info"):
		fn = {"warning": self._vb.warning_box, "error": self._vb.error_box, "success": self._vb.success_box}.get(level, self._vb.info_box)
		return fn(title=str(title), text=str(text), window=self.form.wnd)

	def confirm(self, title, text) -> bool:
		return self._vb.confirm(title=str(title), text=str(text), window=self.form.wnd)

	def prompt(self, title, text="", default=""):
		lbl = f"{title}: {text}" if text else str(title)
		return self._vb.input(title=lbl, text=str(default), window=self.form.wnd)

	def open_file(self, title="Open File", wildcard=None):
		f = self._vb.form(window=self.form.wnd, config={"label": str(title)})
		f.add("tree", "dir_tree", path=os.getcwd(), include_files=True, label=str(title))
		f.add("ok", "button", label="Open")
		f.add("cancel", "button", label="Cancel")
		return f.get("tree") if f.open() == "ok" else None

	def save_file(self, title="Save File", wildcard=None):
		return self.prompt(title, "Enter file path:", os.getcwd())

	def open_folder(self, title="Select Folder"):
		f = self._vb.form(window=self.form.wnd, config={"label": str(title)})
		f.add("tree", "dir_tree", path=os.getcwd(), include_files=False, label=str(title))
		f.add("ok", "button", label="Select")
		f.add("cancel", "button", label="Cancel")
		return f.get("tree") if f.open() == "ok" else None

	def close(self):
		self.form._pending_btn = -1

	def frameUpdate(self):
		self.form.mainloop()
		while True:
			self.form.wnd.frameUpdate()
			self._scheduler.update()
			for im, fn in self._shortcuts:
				if im.pressed("_sc", self.form.wnd):
					fn()
			res = self.form.frameUpdate()
			if res == -1:
				if self._close_cb and self._close_cb() is False:
					continue
				return -1
			if res is not None and any(it["name"] == res and it["kind"] == "button" for it in self.form.items):
				self.form.wnd.wait(5)
				return res


# ==============================================================================
# PUBLIC FACTORY CLASS (100% backwards-compatible with gui.Window)
# ==============================================================================

class Window:
	"""Cross-platform accessible GUI Window factory."""

	def __new__(cls, title="PyAudioGaming App", size=(500, 400), backend="auto", window=None):
		chosen = detect_gui_backend(backend)
		if chosen == "wx":
			try:
				return WxWindow(title, size)
			except Exception:
				pass
		if chosen == "qt":
			try:
				return QtWindow(title, size)
			except Exception:
				pass
		if chosen == "tk":
			try:
				return TkWindow(title, size)
			except Exception:
				pass
		return AudioWindow(title, size, window=window)
