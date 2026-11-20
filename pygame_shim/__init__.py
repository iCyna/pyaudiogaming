# -*- coding: utf-8 -*-
"""Android BeeWare native pygame shim for PyAudioGaming."""
from .locals import *  # noqa: F401,F403
from .rect import Rect
from .surface import Surface
from . import locals
from . import display
from . import event
from . import time
from . import key
from . import draw
from . import font
from . import scrap
from . import mouse
from . import _android_bridge

error = RuntimeError
_INIT_DONE = False


def init():
    global _INIT_DONE
    display.init()
    font.init()
    _INIT_DONE = True
    return (6, 0)


def quit():
    global _INIT_DONE
    display.quit()
    font.quit()
    _INIT_DONE = False


def get_init():
    return _INIT_DONE
