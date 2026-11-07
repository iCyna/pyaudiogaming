# -*- coding: utf-8 -*-
# copyright 2025 belong ihcyna (Labubu)<phucnggo29@gmail.com>.
#wx gui app of pyaudiogaming

from . import inputBox
wx = None


class Window:
    def __new__(cls, title="wxPython App", size=(400, 300)):
        global wx
        if inputBox.system.get_platform()["os"] in ("linux", "macos"):
            try: return QtWindow(title, size)
            except ImportError: return AudioWindow(title, size)
        wx = inputBox.check()
        if wx is None: return AudioWindow(title, size)
        return super().__new__(cls)

    def __init__(self, title="wxPython App", size=(400, 300)):
        self.app = wx.GetApp() or wx.App(False)
        self.frame = wx.Frame(None, title=title, size=size)
        self.panel = wx.Panel(self.frame)
        self.elements = {}
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.sizer)

    def button(self, label, handler, font=None, color=None):
        """Thêm một nút bấm vào giao diện."""
        button = wx.Button(self.panel, label=label)
        if font:
            button.SetFont(font)
        if color:
            button.SetForegroundColour(color)
        button.Bind(wx.EVT_BUTTON, handler)
        self.sizer.Add(button, 0, wx.ALL | wx.EXPAND, 5)
        self.elements[label] = button
        return button

    def print(self, text, font=None, color=None):
        """Thêm một dòng chữ hiển thị."""
        static_text = wx.StaticText(self.panel, label=text)
        if font:
            static_text.SetFont(font)
        if color:
            static_text.SetForegroundColour(color)
        self.sizer.Add(static_text, 0, wx.ALL, 5)
        self.elements[text] = static_text
        return static_text

    def input(self, label, value="", font=None):
        """Thêm một ô nhập liệu với nhãn."""
        box_sizer = wx.BoxSizer(wx.HORIZONTAL)
        static_text = wx.StaticText(self.panel, label=label)
        text_ctrl = wx.TextCtrl(self.panel, value=value)
        if font:
            static_text.SetFont(font)
            text_ctrl.SetFont(font)
        box_sizer.Add(static_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        box_sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        self.sizer.Add(box_sizer, 0, wx.EXPAND)
        self.elements[label] = text_ctrl
        return text_ctrl

    def remove(self, label):
        """Xóa một thành phần khỏi giao diện."""
        if label in self.elements:
            element = self.elements[label]
            element.Destroy()
            del self.elements[label]
            self.sizer.Layout()
        else:
            print(f"Không tìm thấy thành phần có nhãn: {label}")

    def edit(self, label, font=None, color=None):
        """Thay đổi kiểu của một thành phần đã thêm."""
        element = self.elements.get(label)
        if not element:
            print(f"Không tìm thấy thành phần có nhãn: {label}")
            return
        if font:
            element.SetFont(font)
        if color:
            element.SetForegroundColour(color)

    def frameUpdate(self):
        """Hiển thị giao diện."""
        self.frame.Show()
        self.app.MainLoop()


class AudioWindow:
    """SDL audio controls when native wx controls are unavailable."""
    def __init__(self, title, size):
        from . import vb
        from .utils import get_window
        if get_window() is None:
            raise RuntimeError("Initialize window.Window before using audio GUI controls")
        self.form = vb.form(config={"label": title})
        self.elements = {}

    def button(self, label, handler, font=None, color=None):
        item = self.form.add(label, callback=lambda form, item: handler(item), config={"label": label})
        self.elements[label] = item
        return item

    def input(self, label, value="", font=None):
        item = self.form.add(label, "input", value, config={"label": label})
        self.elements[label] = item
        return item

    def print(self, text, font=None, color=None):
        self.form.wnd.say(text)
        return text

    def remove(self, label):
        item = self.elements.pop(label, None)
        if item: self.form.items.remove(item)
        self.form.cursor = max(0, min(self.form.cursor, len(self.form.items) - 1))

    def edit(self, label, font=None, color=None): return self.elements.get(label)
    def frameUpdate(self): return self.form.run()


class QtWindow:
    """Lazy native Qt widgets for Linux and macOS."""
    def __init__(self, title, size):
        from PySide6 import QtWidgets
        self.qt = QtWidgets
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.frame = QtWidgets.QWidget()
        self.frame.setWindowTitle(title)
        self.frame.resize(*size)
        self.layout = QtWidgets.QVBoxLayout(self.frame)
        self.elements = {}

    def _add(self, label, widget, font=None, color=None):
        widget.setAccessibleName(label)
        if font is not None: widget.setFont(font)
        if color is not None:
            from PySide6.QtGui import QColor, QPalette
            palette = widget.palette()
            palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
            palette.setColor(QPalette.ColorRole.Text, QColor(color))
            widget.setPalette(palette)
        self.layout.addWidget(widget)
        self.elements[label] = widget
        return widget

    def button(self, label, handler, font=None, color=None):
        widget = self._add(label, self.qt.QPushButton(label), font, color)
        widget.clicked.connect(lambda checked=False: handler(widget))
        return widget

    def print(self, text, font=None, color=None):
        return self._add(text, self.qt.QLabel(text), font, color)

    def input(self, label, value="", font=None):
        caption = self.qt.QLabel(label)
        widget = self._add(label, self.qt.QLineEdit(value), font)
        caption.setBuddy(widget)
        self.layout.insertWidget(self.layout.count() - 1, caption)
        widget._caption = caption
        return widget

    def remove(self, label):
        widget = self.elements.pop(label, None)
        if widget is not None:
            if hasattr(widget, "_caption"): widget._caption.deleteLater()
            widget.deleteLater()

    def edit(self, label, font=None, color=None):
        widget = self.elements.get(label)
        if widget is not None:
            if font is not None: widget.setFont(font)
            if color is not None:
                from PySide6.QtGui import QColor, QPalette
                palette = widget.palette()
                palette.setColor(QPalette.ColorRole.WindowText, QColor(color))
                palette.setColor(QPalette.ColorRole.Text, QColor(color))
                widget.setPalette(palette)
        return widget

    def frameUpdate(self):
        self.frame.show()
        return self.app.exec()
