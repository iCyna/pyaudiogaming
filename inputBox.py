# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# Native input, message, and file dialogs with accessible SDL fallbacks.
# Supports Windows, Linux, macOS, Android, iOS, and Web.

import ctypes
import os
import shutil
import subprocess
import threading

from . import buffer, system

wx, _app = None, None
INFO, ERROR, WARNING, QUESTION = 2052, 516, 260, 1034
CONFIG = {"ok-text": "OK", "yes-text": "Yes", "no-text": "No", "cancel-text": "Cancel", "form": {}}


# ---------------------------------------------------------------------------
# Desktop Toolkit Checks (Qt / wxPython)
# ---------------------------------------------------------------------------

def check_qt():
    global _app
    if system.get_platform()["os"] not in ("windows", "linux", "macos"):
        return None
    QtWidgets = None
    for mod_name in ("PySide6", "PyQt6", "PyQt5"):
        try:
            mod = __import__(f"{mod_name}.QtWidgets", fromlist=["QtWidgets"])
            QtWidgets = mod
            break
        except ImportError:
            continue
    if QtWidgets is None:
        return None
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return QtWidgets


def check():
    global wx, _app
    if system.get_platform()["os"] not in ("windows", "linux", "macos"):
        return None
    try:
        import wx as api
    except ImportError:
        return None
    wx = api
    _app = wx.GetApp() or wx.App(False)
    return wx


def _show(title, dialog, read):
    buffer.names_window.append(title)
    try:
        return read(dialog.ShowModal())
    finally:
        try:
            dialog.Destroy()
        except Exception:
            pass
        if title in buffer.names_window:
            buffer.names_window.remove(title)


# ---------------------------------------------------------------------------
# Android Native Dialogs (Chaquopy AlertDialog — TalkBack accessible)
# ---------------------------------------------------------------------------

def _android_run_dialog(build_fn):
    """Run an Android AlertDialog synchronously on the UI thread and return its result."""
    act, bridge = system.get_android_activity()
    if act is None or bridge != "chaquopy":
        return False, None
    try:
        from java import jclass, dynamic_proxy
    except Exception:
        return False, None

    done = threading.Event()
    box = {"result": None, "ok": False}

    def _finish(val):
        if not done.is_set():
            box["result"] = val
            box["ok"] = True
            done.set()

    Runnable = jclass("java.lang.Runnable")

    class _UiTask(dynamic_proxy(Runnable)):
        def run(self):
            try:
                build_fn(act, jclass, dynamic_proxy, _finish)
            except Exception:
                done.set()

    task_ref = _UiTask()
    act.runOnUiThread(task_ref)
    done.wait()
    return box["ok"], box["result"]


def _android_kbt(title, message, password=False, cfg=None):
    cfg = {**CONFIG, **(cfg or {})}

    def _build(act, jclass, dynamic_proxy, finish):
        Builder = jclass("android.app.AlertDialog$Builder")
        EditText = jclass("android.widget.EditText")
        InputType = jclass("android.text.InputType")
        OnClick = jclass("android.content.DialogInterface$OnClickListener")
        OnCancel = jclass("android.content.DialogInterface$OnCancelListener")

        edit = EditText(act)
        if password:
            edit.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD)
        else:
            edit.setInputType(InputType.TYPE_CLASS_TEXT)
        edit.setSingleLine(True)

        class _OkClick(dynamic_proxy(OnClick)):
            def onClick(self, dlg, which):
                try:
                    finish(str(edit.getText().toString()))
                except Exception:
                    finish("")

        class _CancelClick(dynamic_proxy(OnClick)):
            def onClick(self, dlg, which):
                finish(None)

        class _CancelListen(dynamic_proxy(OnCancel)):
            def onCancel(self, dlg):
                finish(None)

        b = Builder(act)
        b.setTitle(str(title))
        if message:
            b.setMessage(str(message))
        b.setView(edit)
        b.setPositiveButton(str(cfg["ok-text"]), _OkClick())
        b.setNegativeButton(str(cfg["cancel-text"]), _CancelClick())
        b.setOnCancelListener(_CancelListen())
        b.create().show()

    return _android_run_dialog(_build)


def _android_kbc(title, message, choices, multi=False, cfg=None):
    cfg = {**CONFIG, **(cfg or {})}
    str_choices = [str(c) for c in choices]

    def _build(act, jclass, dynamic_proxy, finish):
        from java import jarray, jboolean
        Builder = jclass("android.app.AlertDialog$Builder")
        CharSequence = jclass("java.lang.CharSequence")
        OnClick = jclass("android.content.DialogInterface$OnClickListener")
        OnMulti = jclass("android.content.DialogInterface$OnMultiChoiceClickListener")
        OnCancel = jclass("android.content.DialogInterface$OnCancelListener")

        items = jarray(CharSequence)(str_choices)
        selected_single = [0]
        selected_multi = [False] * len(str_choices)

        class _CancelClick(dynamic_proxy(OnClick)):
            def onClick(self, dlg, which):
                finish(None)

        class _CancelListen(dynamic_proxy(OnCancel)):
            def onCancel(self, dlg):
                finish(None)

        b = Builder(act)
        b.setTitle(str(title))
        if multi:
            checked = jarray(jboolean)(selected_multi)

            class _MultiClick(dynamic_proxy(OnMulti)):
                def onClick(self, dlg, which, is_checked):
                    if 0 <= which < len(selected_multi):
                        selected_multi[which] = bool(is_checked)

            class _OkMulti(dynamic_proxy(OnClick)):
                def onClick(self, dlg, which):
                    finish([i for i, v in enumerate(selected_multi) if v])

            b.setMultiChoiceItems(items, checked, _MultiClick())
            b.setPositiveButton(str(cfg["ok-text"]), _OkMulti())
        else:
            class _SingleClick(dynamic_proxy(OnClick)):
                def onClick(self, dlg, which):
                    selected_single[0] = int(which)

            class _OkSingle(dynamic_proxy(OnClick)):
                def onClick(self, dlg, which):
                    finish(selected_single[0])

            b.setSingleChoiceItems(items, 0, _SingleClick())
            b.setPositiveButton(str(cfg["ok-text"]), _OkSingle())

        b.setNegativeButton(str(cfg["cancel-text"]), _CancelClick())
        b.setOnCancelListener(_CancelListen())
        b.create().show()

    return _android_run_dialog(_build)


def _android_message(title, message, style=INFO, y=True, n=False, cfg=None):
    cfg = {**CONFIG, **(cfg or {})}

    def _build(act, jclass, dynamic_proxy, finish):
        Builder = jclass("android.app.AlertDialog$Builder")
        OnClick = jclass("android.content.DialogInterface$OnClickListener")
        OnCancel = jclass("android.content.DialogInterface$OnCancelListener")

        class _YesClick(dynamic_proxy(OnClick)):
            def onClick(self, dlg, which):
                finish(y)

        class _NoClick(dynamic_proxy(OnClick)):
            def onClick(self, dlg, which):
                finish(n)

        class _CancelListen(dynamic_proxy(OnCancel)):
            def onCancel(self, dlg):
                finish(n if style == QUESTION else y)

        b = Builder(act)
        b.setTitle(str(title))
        b.setMessage(str(message))
        if style == QUESTION:
            b.setPositiveButton(str(cfg["yes-text"]), _YesClick())
            b.setNegativeButton(str(cfg["no-text"]), _NoClick())
        else:
            b.setPositiveButton(str(cfg["ok-text"]), _YesClick())
        b.setOnCancelListener(_CancelListen())
        b.create().show()

    return _android_run_dialog(_build)


# ---------------------------------------------------------------------------
# Windows Native Zero-Dependency Fallbacks (Win32 API — NVDA/JAWS accessible)
# ---------------------------------------------------------------------------

def _win32_message(title, message, style=INFO, y=True, n=False):
    flags = 0x00000000  # MB_OK
    if style == QUESTION:
        flags = 0x00000004 | 0x00000020  # MB_YESNO | MB_ICONQUESTION
    elif style == ERROR:
        flags = 0x00000010  # MB_ICONERROR
    elif style == WARNING:
        flags = 0x00000030  # MB_ICONWARNING
    else:
        flags = 0x00000040  # MB_ICONINFORMATION
    res = ctypes.windll.user32.MessageBoxW(0, str(message), str(title), flags)
    if style == QUESTION:
        return y if res == 6 else n  # IDYES == 6
    return y


def _win32_file_or_dir_dialog(title, dir_dialog=False):
    # Try standard tkinter filedialog if available, otherwise Win32 comdlg32/shell32
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        try:
            if dir_dialog:
                return filedialog.askdirectory(title=str(title)) or None
            return filedialog.askopenfilename(title=str(title)) or None
        finally:
            root.destroy()
    except Exception:
        pass

    if not dir_dialog:
        class _OPENFILENAMEW(ctypes.Structure):
            _fields_ = [
                ("lStructSize", ctypes.c_uint32),
                ("hwndOwner", ctypes.c_void_p),
                ("hInstance", ctypes.c_void_p),
                ("lpstrFilter", ctypes.c_wchar_p),
                ("lpstrCustomFilter", ctypes.c_wchar_p),
                ("nMaxCustFilter", ctypes.c_uint32),
                ("nFilterIndex", ctypes.c_uint32),
                ("lpstrFile", ctypes.c_wchar_p),
                ("nMaxFile", ctypes.c_uint32),
                ("lpstrFileTitle", ctypes.c_wchar_p),
                ("nMaxFileTitle", ctypes.c_uint32),
                ("lpstrInitialDir", ctypes.c_wchar_p),
                ("lpstrTitle", ctypes.c_wchar_p),
                ("Flags", ctypes.c_uint32),
                ("nFileOffset", ctypes.c_uint16),
                ("nFileExtension", ctypes.c_uint16),
                ("lpstrDefExt", ctypes.c_wchar_p),
                ("lCustData", ctypes.c_ssize_t),
                ("lpfnHook", ctypes.c_void_p),
                ("lpTemplateName", ctypes.c_wchar_p),
                ("pvReserved", ctypes.c_void_p),
                ("dwReserved", ctypes.c_uint32),
                ("FlagsEx", ctypes.c_uint32),
            ]
        buf = ctypes.create_unicode_buffer(32768)
        ofn = _OPENFILENAMEW()
        ofn.lStructSize = ctypes.sizeof(_OPENFILENAMEW)
        ofn.lpstrFilter = "All Files (*.*)\0*.*\0\0"
        ofn.lpstrFile = ctypes.cast(buf, ctypes.c_wchar_p)
        ofn.nMaxFile = len(buf)
        ofn.lpstrTitle = str(title)
        ofn.Flags = 0x00001000 | 0x00000800 | 0x00000008  # FILEMUSTEXIST | PATHMUSTEXIST | NOCHANGEDIR
        if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
            return buf.value or None
        return None
    return None


# ---------------------------------------------------------------------------
# macOS / Linux / Web Native Zero-Dependency Fallbacks
# ---------------------------------------------------------------------------

def _escape_applescript(text):
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def _macos_osascript(script):
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if res.returncode != 0:
            return False, None
        return True, res.stdout.strip()
    except Exception:
        return False, None


def _linux_zenity(args):
    exe = shutil.which("zenity")
    if not exe:
        return False, None
    try:
        res = subprocess.run([exe] + list(args), capture_output=True, text=True)
        if res.returncode != 0:
            return True, None
        return True, res.stdout.strip()
    except Exception:
        return False, None


# ---------------------------------------------------------------------------
# Public Cross-Platform API
# ---------------------------------------------------------------------------

def kbt(self, title, message, password=False, dir_dialog=False, file_dialog=False, config=None):
    os_name = system.get_platform()["os"]

    # 1. Android native AlertDialog
    if os_name == "android":
        if not (dir_dialog or file_dialog):
            ok, val = _android_kbt(title, message, password=password, cfg=config)
            if ok:
                return val

    # 2. Web (Pyodide)
    if os_name == "web" and not (dir_dialog or file_dialog):
        try:
            import js
            val = js.window.prompt(f"{title}\n{message}")
            return None if val is None else str(val)
        except Exception:
            pass

    # 3. Desktop Qt (Linux / macOS preferred, or Windows fallback)
    if os_name in ("linux", "macos"):
        qt = check_qt()
        if qt is not None:
            if dir_dialog:
                return qt.QFileDialog.getExistingDirectory(None, title) or None
            if file_dialog:
                return qt.QFileDialog.getOpenFileName(None, title)[0] or None
            echo = qt.QLineEdit.EchoMode.Password if password else qt.QLineEdit.EchoMode.Normal
            value, accepted = qt.QInputDialog.getText(None, title, message, echo)
            return value if accepted else None

    # 4. Desktop wxPython
    if check() is not None:
        if dir_dialog:
            dialog = wx.DirDialog(None, message, style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        elif file_dialog:
            dialog = wx.FileDialog(None, message, wildcard="All files (*.*)|*.*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        elif password:
            dialog = wx.PasswordEntryDialog(None, message, title)
        else:
            dialog = wx.TextEntryDialog(None, message, title)
        return _show(title, dialog, lambda result: (dialog.GetPath() if dir_dialog or file_dialog else dialog.GetValue()) if result == wx.ID_OK else None)

    # 5. Desktop Qt on Windows (if wxPython absent)
    if os_name == "windows":
        qt = check_qt()
        if qt is not None:
            if dir_dialog:
                return qt.QFileDialog.getExistingDirectory(None, title) or None
            if file_dialog:
                return qt.QFileDialog.getOpenFileName(None, title)[0] or None
            echo = qt.QLineEdit.EchoMode.Password if password else qt.QLineEdit.EchoMode.Normal
            value, accepted = qt.QInputDialog.getText(None, title, message, echo)
            return value if accepted else None
        if dir_dialog or file_dialog:
            return _win32_file_or_dir_dialog(title, dir_dialog=dir_dialog)

    # 6. macOS AppleScript native fallback
    if os_name == "macos":
        t_esc, m_esc = _escape_applescript(title), _escape_applescript(message)
        if dir_dialog:
            ok, out = _macos_osascript(f'POSIX path of (choose folder with prompt "{m_esc}")')
            if ok:
                return out or None
        elif file_dialog:
            ok, out = _macos_osascript(f'POSIX path of (choose file with prompt "{m_esc}")')
            if ok:
                return out or None
        else:
            hidden = " with hidden answer" if password else ""
            ok, out = _macos_osascript(f'text returned of (display dialog "{m_esc}" with title "{t_esc}" default answer ""{hidden})')
            if ok:
                return out

    # 7. Linux zenity native fallback
    if os_name == "linux":
        if dir_dialog:
            ok, out = _linux_zenity(["--file-selection", "--directory", f"--title={title}"])
            if ok:
                return out or None
        elif file_dialog:
            ok, out = _linux_zenity(["--file-selection", f"--title={title}"])
            if ok:
                return out or None

    # 8. Universal accessible SDL (vb) fallback
    from . import vb
    if dir_dialog or file_dialog:
        return vb.input(title + ", " + message, password=False, new_config=config)
    return vb.input(title + ", " + message, password=password, new_config=config)


def kbc(self, title, message, choices, multi=False, config=None):
    if not choices:
        return [] if multi else None
    os_name = system.get_platform()["os"]

    # 1. Android native AlertDialog
    if os_name == "android":
        ok, val = _android_kbc(title, message, choices, multi=multi, cfg=config)
        if ok:
            return val

    # 2. Desktop Qt (Linux / macOS preferred)
    if os_name in ("linux", "macos"):
        qt = check_qt()
        if qt is not None:
            dialog = qt.QDialog()
            dialog.setWindowTitle(title)
            layout = qt.QVBoxLayout(dialog)
            layout.addWidget(qt.QLabel(message))
            listing = qt.QListWidget()
            listing.addItems([str(choice) for choice in choices])
            listing.setSelectionMode(qt.QAbstractItemView.SelectionMode.MultiSelection if multi else qt.QAbstractItemView.SelectionMode.SingleSelection)
            if not multi:
                listing.setCurrentRow(0)
            layout.addWidget(listing)
            buttons = qt.QDialogButtonBox(qt.QDialogButtonBox.StandardButton.Ok | qt.QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() != qt.QDialog.DialogCode.Accepted:
                return None
            return sorted(listing.row(item) for item in listing.selectedItems()) if multi else listing.currentRow()

    # 3. Desktop wxPython
    if check() is not None:
        dialog = (wx.MultiChoiceDialog if multi else wx.SingleChoiceDialog)(None, message, title, [str(c) for c in choices])
        return _show(title, dialog, lambda result: (dialog.GetSelections() if multi else dialog.GetSelection()) if result == wx.ID_OK else None)

    # 4. macOS AppleScript native fallback
    if os_name == "macos":
        t_esc, m_esc = _escape_applescript(title), _escape_applescript(message)
        items_as = ", ".join(f'"{_escape_applescript(c)}"' for c in choices)
        mult_flag = " with multiple selections allowed" if multi else ""
        ok, out = _macos_osascript(f'choose from list {{{items_as}}} with title "{t_esc}" with prompt "{m_esc}"{mult_flag}')
        if ok and out and out != "false":
            str_choices = [str(c) for c in choices]
            if multi:
                picked = [p.strip() for p in out.split(",")]
                return [i for i, c in enumerate(str_choices) if c in picked]
            return str_choices.index(out) if out in str_choices else 0

    # 5. Universal accessible SDL (vb) fallback
    from . import vb
    cfg = {**CONFIG, **(config or {})}
    form = vb.form(config={**cfg["form"], "label": title + ", " + message})
    if multi:
        for i, choice in enumerate(choices):
            form.add(str(i), "check", False, config={"label": str(choice)})
    else:
        form.add("choice", "list", 0, choices=choices, config={"label": message})
    form.add("ok", config={"label": cfg["ok-text"]})
    if form.run() == -1:
        return None
    return [i for i in range(len(choices)) if form.values()[str(i)]] if multi else form.values()["choice"]


def dialogMessage(title, message, style=INFO, y=True, n=False, config=None):
    os_name = system.get_platform()["os"]

    # 1. Android native AlertDialog
    if os_name == "android":
        ok, val = _android_message(title, message, style=style, y=y, n=n, cfg=config)
        if ok:
            return val

    # 2. Web (Pyodide)
    if os_name == "web":
        try:
            import js
            if style == QUESTION:
                return y if js.window.confirm(f"{title}\n{message}") else n
            js.window.alert(f"{title}\n{message}")
            return y
        except Exception:
            pass

    # 3. Desktop Qt (Linux / macOS preferred)
    if os_name in ("linux", "macos"):
        qt = check_qt()
        if qt is not None:
            if style == QUESTION:
                return y if qt.QMessageBox.question(None, title, message) == qt.QMessageBox.StandardButton.Yes else n
            show = qt.QMessageBox.critical if style == ERROR else qt.QMessageBox.warning if style == WARNING else qt.QMessageBox.information
            show(None, title, message)
            return y

    # 4. Desktop wxPython
    if check() is not None:
        dialog = wx.MessageDialog(None, message, title, style)
        return _show(title, dialog, lambda result: y if result in (wx.ID_YES, wx.ID_OK) else n)

    # 5. Windows native Win32 MessageBoxW (zero dependencies, screen-reader accessible)
    if os_name == "windows":
        try:
            return _win32_message(title, message, style=style, y=y, n=n)
        except Exception:
            pass

    # 6. macOS AppleScript native fallback
    if os_name == "macos":
        t_esc, m_esc = _escape_applescript(title), _escape_applescript(message)
        cfg = {**CONFIG, **(config or {})}
        if style == QUESTION:
            yb, nb = _escape_applescript(cfg["yes-text"]), _escape_applescript(cfg["no-text"])
            ok, out = _macos_osascript(f'button returned of (display dialog "{m_esc}" with title "{t_esc}" buttons {{"{nb}", "{yb}"}} default button "{yb}")')
            if ok:
                return y if out == cfg["yes-text"] else n
        else:
            ok, _ = _macos_osascript(f'display dialog "{m_esc}" with title "{t_esc}" buttons {{"OK"}} default button "OK"')
            if ok:
                return y

    # 7. Universal accessible SDL (vb) fallback
    from . import vb
    cfg = {**CONFIG, **(config or {})}
    if style == QUESTION:
        form = vb.form(config={**cfg["form"], "label": title + ", " + message})
        form.add("yes", config={"label": cfg["yes-text"]})
        form.add("no", config={"label": cfg["no-text"]})
        return y if form.run() == "yes" else n
    vb.message(title + ", " + message)
    return y
