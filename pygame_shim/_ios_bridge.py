# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# iOS UIKit/Rubicon-ObjC native bridge for the pygame shim.
# Supports iOS.

import ctypes
import sys
import threading

from . import locals as _L
from . import event as _event
from . import key as _key
from . import mouse as _mouse

_IS_IOS = (sys.platform == "ios")
_HAS_RUBICON = False
_ObjCClass = None
_ObjCInstance = None
_objc_method = None
_send_super = None
_CGRect = None
_CGPoint = None
_CGSize = None
_ns_from_py = None

if _IS_IOS:
    try:
        from rubicon.objc import ObjCClass, ObjCInstance, objc_method, send_super, CGRect, CGPoint, CGSize, py_from_ns, ns_from_py
        _ObjCClass, _ObjCInstance = ObjCClass, ObjCInstance
        _objc_method, _send_super = objc_method, send_super
        _CGRect, _CGPoint, _CGSize, _ns_from_py = CGRect, CGPoint, CGSize, ns_from_py
        _HAS_RUBICON = True
    except Exception:
        _HAS_RUBICON = False

_LOCK = threading.Lock()
_BOOTSTRAPPED = False
_VIEW = None
_OVERLAY_LABEL = None
_WINDOW = None
_LOGICAL_SIZE = (800, 600)
_TOUCH_IDS = {}
_NEXT_TOUCH_ID = 1
_LAST_TOUCH = {}


def set_fullscreen(enabled=True):
    """Toggle iOS status bar visibility safely on the UIKit main thread."""
    if not is_ios_available():
        return False
    want_fs = bool(enabled)

    def _do():
        try:
            UIApplication = _ObjCClass("UIApplication")
            app = UIApplication.sharedApplication
            if app is not None and hasattr(app, "setStatusBarHidden_withAnimation_"):
                app.setStatusBarHidden_withAnimation_(want_fs, 0)
        except Exception:
            pass
        try:
            vc = _get_top_vc()
            if vc is not None and hasattr(vc, "setNeedsStatusBarAppearanceUpdate"):
                vc.setNeedsStatusBarAppearanceUpdate()
        except Exception:
            pass

    _run_on_main(_do)
    return True


def is_ios_available():
    return _IS_IOS and _HAS_RUBICON


def _run_on_main(fn):
    """Execute fn on the iOS main UIKit thread."""
    if not _HAS_RUBICON:
        return
    try:
        NSThread = _ObjCClass("NSThread")
        if NSThread.isMainThread:
            fn()
            return
        NSOperationQueue = _ObjCClass("NSOperationQueue")
        from rubicon.objc import Block

        @Block
        def _blk():
            try:
                fn()
            except Exception:
                pass

        NSOperationQueue.mainQueue.addOperationWithBlock(_blk)
    except Exception:
        try:
            fn()
        except Exception:
            pass


def _get_key_window():
    if not _HAS_RUBICON:
        return None
    try:
        UIApplication = _ObjCClass("UIApplication")
        app = UIApplication.sharedApplication
        if app is None:
            return None
        if hasattr(app, "connectedScenes"):
            scenes = app.connectedScenes
            if scenes is not None:
                for sc in scenes.allObjects():
                    if hasattr(sc, "windows"):
                        wins = sc.windows
                        if wins is not None and len(wins) > 0:
                            for w in wins:
                                if getattr(w, "isKeyWindow", False):
                                    return w
                            return wins[0]
        if hasattr(app, "keyWindow") and app.keyWindow is not None:
            return app.keyWindow
        wins = getattr(app, "windows", None)
        if wins is not None and len(wins) > 0:
            return wins[0]
    except Exception:
        pass
    return None


def _get_top_vc():
    win = _WINDOW or _get_key_window()
    if win is None:
        return None
    vc = getattr(win, "rootViewController", None)
    while vc is not None and getattr(vc, "presentedViewController", None) is not None:
        vc = vc.presentedViewController
    return vc


def _dispatch_touches(view, touches, action):
    """Convert UIKit UITouch set into pygame FINGERDOWN/MOTION/UP events."""
    global _NEXT_TOUCH_ID
    if touches is None or view is None:
        return
    try:
        bounds = view.bounds
        vw = max(1.0, float(bounds.size.width))
        vh = max(1.0, float(bounds.size.height))
    except Exception:
        vw, vh = 1.0, 1.0
    lw, lh = _LOGICAL_SIZE
    t_list = list(touches.allObjects()) if hasattr(touches, "allObjects") else list(touches)
    for t in t_list:
        ptr = int(getattr(t, "ptr", id(t)).value) if hasattr(getattr(t, "ptr", None), "value") else id(t)
        pt = t.locationInView(view)
        nx = max(0.0, min(1.0, float(pt.x) / vw))
        ny = max(0.0, min(1.0, float(pt.y) / vh))
        px, py = int(nx * lw), int(ny * lh)

        if action == 0:
            pid = _TOUCH_IDS.get(ptr)
            if pid is None:
                pid = _NEXT_TOUCH_ID
                _NEXT_TOUCH_ID += 1
                _TOUCH_IDS[ptr] = pid
            _LAST_TOUCH[pid] = (nx, ny)
            _event.post(_event.Event(_L.FINGERDOWN, {
                "finger_id": pid, "x": nx, "y": ny, "dx": 0.0, "dy": 0.0, "touch_id": 0
            }))
            _mouse._update_pos((px, py))
            if len(_TOUCH_IDS) == 1:
                _mouse._update_button(1, True)
                _event.post(_event.Event(_L.MOUSEBUTTONDOWN, {"pos": (px, py), "button": 1, "touch": True}))
        elif action == 1:
            pid = _TOUCH_IDS.get(ptr)
            if pid is None:
                continue
            prev = _LAST_TOUCH.get(pid, (nx, ny))
            dx, dy = nx - prev[0], ny - prev[1]
            _LAST_TOUCH[pid] = (nx, ny)
            _event.post(_event.Event(_L.FINGERMOTION, {
                "finger_id": pid, "x": nx, "y": ny, "dx": dx, "dy": dy, "touch_id": 0
            }))
            _mouse._update_pos((px, py))
            _event.post(_event.Event(_L.MOUSEMOTION, {"pos": (px, py), "rel": (0, 0), "buttons": (1, 0, 0), "touch": True}))
        else:
            pid = _TOUCH_IDS.pop(ptr, None)
            if pid is None:
                continue
            prev = _LAST_TOUCH.pop(pid, (nx, ny))
            dx, dy = nx - prev[0], ny - prev[1]
            _event.post(_event.Event(_L.FINGERUP, {
                "finger_id": pid, "x": nx, "y": ny, "dx": dx, "dy": dy, "touch_id": 0
            }))
            _mouse._update_pos((px, py))
            if not _TOUCH_IDS:
                _mouse._update_button(1, False)
                _event.post(_event.Event(_L.MOUSEBUTTONUP, {"pos": (px, py), "button": 1, "touch": True}))


def bootstrap_ios():
    """Attach a VoiceOver-friendly UIKit multi-touch + keyboard view on iOS."""
    global _BOOTSTRAPPED, _VIEW, _OVERLAY_LABEL, _WINDOW
    with _LOCK:
        if _BOOTSTRAPPED:
            return _VIEW is not None
        if not is_ios_available():
            _BOOTSTRAPPED = True
            return False

    done = threading.Event()

    def _setup():
        global _BOOTSTRAPPED, _VIEW, _OVERLAY_LABEL, _WINDOW
        try:
            UIView = _ObjCClass("UIView")
            UILabel = _ObjCClass("UILabel")
            UIColor = _ObjCClass("UIColor")
            UIScreen = _ObjCClass("UIScreen")
            UIWindow = _ObjCClass("UIWindow")
            UIViewController = _ObjCClass("UIViewController")

            class PyagIOSTouchView(UIView):
                @_objc_method
                def canBecomeFirstResponder(self) -> bool:
                    return True

                @_objc_method
                def hasText(self) -> bool:
                    return True

                @_objc_method
                def insertText_(self, text) -> None:
                    s = str(text)
                    if s == "\n":
                        _key._set_key_state(_L.K_RETURN, True, 0)
                        _event.post(_event.Event(_L.KEYDOWN, {"key": _L.K_RETURN, "mod": 0, "unicode": "\r", "scancode": 0}))
                        _key._set_key_state(_L.K_RETURN, False, 0)
                        _event.post(_event.Event(_L.KEYUP, {"key": _L.K_RETURN, "mod": 0, "unicode": "", "scancode": 0}))
                    elif s:
                        _event.post(_event.Event(_L.TEXTINPUT, {"text": s}))

                @_objc_method
                def deleteBackward(self) -> None:
                    _key._set_key_state(_L.K_BACKSPACE, True, 0)
                    _event.post(_event.Event(_L.KEYDOWN, {"key": _L.K_BACKSPACE, "mod": 0, "unicode": "\b", "scancode": 0}))
                    _key._set_key_state(_L.K_BACKSPACE, False, 0)
                    _event.post(_event.Event(_L.KEYUP, {"key": _L.K_BACKSPACE, "mod": 0, "unicode": "", "scancode": 0}))

                @_objc_method
                def touchesBegan_withEvent_(self, touches, ev) -> None:
                    _dispatch_touches(self, touches, 0)

                @_objc_method
                def touchesMoved_withEvent_(self, touches, ev) -> None:
                    _dispatch_touches(self, touches, 1)

                @_objc_method
                def touchesEnded_withEvent_(self, touches, ev) -> None:
                    _dispatch_touches(self, touches, 2)

                @_objc_method
                def touchesCancelled_withEvent_(self, touches, ev) -> None:
                    _dispatch_touches(self, touches, 2)

            win = _get_key_window()
            bounds = UIScreen.mainScreen.bounds
            if win is None:
                win = UIWindow.alloc().initWithFrame(bounds)
                vc = UIViewController.alloc().init()
                win.rootViewController = vc
                win.makeKeyAndVisible()
            _WINDOW = win

            view = PyagIOSTouchView.alloc().initWithFrame(bounds)
            view.multipleTouchEnabled = True
            view.userInteractionEnabled = True
            view.backgroundColor = UIColor.colorWithRed(0.06, green=0.07, blue=0.09, alpha=1.0)
            # UIAccessibilityTraitAllowsDirectInteraction (0x2000) lets VoiceOver pass gestures straight to the audio game
            try:
                view.isAccessibilityElement = True
                view.accessibilityTraits = 0x2000
            except Exception:
                pass

            lbl = UILabel.alloc().initWithFrame(_CGRect(_CGPoint(16.0, 48.0), _CGSize(max(100.0, float(bounds.size.width) - 32.0), max(100.0, float(bounds.size.height) - 96.0))))
            lbl.numberOfLines = 0
            lbl.textColor = UIColor.whiteColor
            lbl.text = ""
            view.addSubview(lbl)

            if win.rootViewController is not None:
                win.rootViewController.view = view
            else:
                win.addSubview(view)

            _VIEW = view
            _OVERLAY_LABEL = lbl
            _BOOTSTRAPPED = True
        except Exception as exc:
            print(f"[pygame_shim:ios] Bootstrap warning: {exc}")
            _BOOTSTRAPPED = True
        finally:
            done.set()

    _run_on_main(_setup)
    done.wait(2.0)
    return _VIEW is not None


def set_logical_size(w, h):
    global _LOGICAL_SIZE
    _LOGICAL_SIZE = (max(1, int(w)), max(1, int(h)))


def set_title(title):
    return None


def set_overlay_text(text, is_error=False):
    if not is_ios_available() or _OVERLAY_LABEL is None:
        return
    def _upd():
        try:
            UIColor = _ObjCClass("UIColor")
            _OVERLAY_LABEL.text = str(text or "")
            _OVERLAY_LABEL.textColor = UIColor.redColor if is_error else UIColor.whiteColor
        except Exception:
            pass
    _run_on_main(_upd)


def show_keyboard():
    if not is_ios_available() or _VIEW is None:
        return
    _run_on_main(lambda: _VIEW.becomeFirstResponder())


def hide_keyboard():
    if not is_ios_available() or _VIEW is None:
        return
    _run_on_main(lambda: _VIEW.resignFirstResponder())


def set_clipboard(text):
    if not is_ios_available():
        return False
    try:
        UIPasteboard = _ObjCClass("UIPasteboard")
        UIPasteboard.generalPasteboard.string = str(text or "")
        return True
    except Exception:
        return False


def get_clipboard():
    if not is_ios_available():
        return ""
    try:
        UIPasteboard = _ObjCClass("UIPasteboard")
        val = UIPasteboard.generalPasteboard.string
        return str(val) if val is not None else ""
    except Exception:
        return ""


def show_error_dialog(title, message):
    """Show native iOS UIAlertController with Copy and Close buttons."""
    if not is_ios_available():
        return False
    safe_title = str(title or "Error")
    safe_msg = str(message or "")
    set_overlay_text(f"{safe_title}\n{safe_msg}", is_error=True)
    shown = [False]
    done = threading.Event()

    def _present():
        try:
            UIAlertController = _ObjCClass("UIAlertController")
            UIAlertAction = _ObjCClass("UIAlertAction")
            from rubicon.objc import Block

            vc = _get_top_vc()
            if vc is None:
                return
            alert = UIAlertController.alertControllerWithTitle(safe_title, message=safe_msg[:3000], preferredStyle=1)

            @Block
            def _on_copy(action):
                set_clipboard(safe_msg)

            @Block
            def _on_close(action):
                pass

            alert.addAction(UIAlertAction.actionWithTitle("Copy", style=0, handler=_on_copy))
            alert.addAction(UIAlertAction.actionWithTitle("Close", style=1, handler=_on_close))
            vc.presentViewController(alert, animated=True, completion=None)
            shown[0] = True
        except Exception:
            pass
        finally:
            done.set()

    _run_on_main(_present)
    done.wait(2.0)
    return shown[0]


def close_app():
    return False
