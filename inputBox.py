# -*- coding: utf-8 -*-
"""Native desktop dialogs with SDL audio fallbacks."""
from . import buffer, system
wx, _app = None, None
INFO, ERROR, WARNING, QUESTION = 2052, 516, 260, 1034
CONFIG = {"ok-text": "OK", "yes-text": "Yes", "no-text": "No", "form": {}}

def check_qt():
    global _app
    if system.get_platform()["os"] not in ("linux", "macos"): return None
    try: from PySide6 import QtWidgets
    except ImportError: return None
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return QtWidgets

def check():
    global wx, _app
    if system.get_platform()["os"] not in ("windows", "linux", "macos"): return None
    try: import wx as api
    except ImportError: return None
    wx = api
    _app = wx.GetApp() or wx.App(False)
    return wx

def _show(title, dialog, read):
    buffer.names_window.append(title)
    try: return read(dialog.ShowModal())
    finally:
        dialog.Destroy()
        buffer.names_window.remove(title)

def kbt(self, title, message, password=False, dir_dialog=False, file_dialog=False, config=None):
    qt = check_qt()
    if qt is not None:
        if dir_dialog: return qt.QFileDialog.getExistingDirectory(None, title) or None
        if file_dialog: return qt.QFileDialog.getOpenFileName(None, title)[0] or None
        value, accepted = qt.QInputDialog.getText(None, title, message,
            qt.QLineEdit.EchoMode.Password if password else qt.QLineEdit.EchoMode.Normal)
        return value if accepted else None
    if check() is None:
        from . import vb
        if dir_dialog or file_dialog: raise RuntimeError("File and directory dialogs require wxPython on desktop")
        return vb.input(title + ", " + message, password=password, new_config=config)
    if dir_dialog: dialog = wx.DirDialog(None, message, style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
    elif file_dialog: dialog = wx.FileDialog(None, message, wildcard="All files (*.*)|*.*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
    elif password: dialog = wx.PasswordEntryDialog(None, message, title)
    else: dialog = wx.TextEntryDialog(None, message, title)
    return _show(title, dialog, lambda result: (dialog.GetPath() if dir_dialog or file_dialog else dialog.GetValue()) if result == wx.ID_OK else None)

def kbc(self, title, message, choices, multi=False, config=None):
    if not choices: return [] if multi else None
    qt = check_qt()
    if qt is not None:
        dialog = qt.QDialog()
        dialog.setWindowTitle(title)
        layout = qt.QVBoxLayout(dialog)
        layout.addWidget(qt.QLabel(message))
        listing = qt.QListWidget()
        listing.addItems([str(choice) for choice in choices])
        listing.setSelectionMode(qt.QAbstractItemView.SelectionMode.MultiSelection if multi else qt.QAbstractItemView.SelectionMode.SingleSelection)
        if not multi: listing.setCurrentRow(0)
        layout.addWidget(listing)
        buttons = qt.QDialogButtonBox(qt.QDialogButtonBox.StandardButton.Ok | qt.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != qt.QDialog.DialogCode.Accepted: return None
        return sorted(listing.row(item) for item in listing.selectedItems()) if multi else listing.currentRow()
    if check() is None:
        from . import vb
        cfg = {**CONFIG, **(config or {})}
        form = vb.form(config={**cfg["form"], "label": title + ", " + message})
        if multi:
            for i, choice in enumerate(choices): form.add(str(i), "check", False, config={"label": str(choice)})
        else: form.add("choice", "list", 0, choices=choices, config={"label": message})
        form.add("ok", config={"label": cfg["ok-text"]})
        if form.run() == -1: return None
        return [i for i in range(len(choices)) if form.values()[str(i)]] if multi else form.values()["choice"]
    dialog = (wx.MultiChoiceDialog if multi else wx.SingleChoiceDialog)(None, message, title, choices)
    return _show(title, dialog, lambda result: (dialog.GetSelections() if multi else dialog.GetSelection()) if result == wx.ID_OK else None)

def dialogMessage(title, message, style=INFO, y=True, n=False, config=None):
    qt = check_qt()
    if qt is not None:
        if style == QUESTION:
            return y if qt.QMessageBox.question(None, title, message) == qt.QMessageBox.StandardButton.Yes else n
        show = qt.QMessageBox.critical if style == ERROR else qt.QMessageBox.warning if style == WARNING else qt.QMessageBox.information
        show(None, title, message)
        return y
    if check() is None:
        from . import vb
        cfg = {**CONFIG, **(config or {})}
        if style == QUESTION:
            form = vb.form(config={**cfg["form"], "label": title + ", " + message})
            form.add("yes", config={"label": cfg["yes-text"]})
            form.add("no", config={"label": cfg["no-text"]})
            return y if form.run() == "yes" else n
        vb.message(title + ", " + message)
        return y
    dialog = wx.MessageDialog(None, message, title, style)
    return _show(title, dialog, lambda result: y if result in (wx.ID_YES, wx.ID_OK) else n)
