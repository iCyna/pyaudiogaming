# -*- coding: utf-8 -*-
"""Thread-safe pygame.event queue shim."""
from collections import deque
import threading

_LOCK = threading.Lock()
_QUEUE = deque()


class Event:
    def __init__(self, event_type, dict_obj=None, **kwargs):
        self.type = int(event_type)
        data = {}
        if isinstance(dict_obj, dict):
            data.update(dict_obj)
        data.update(kwargs)
        for k, v in data.items():
            setattr(self, k, v)
        self.__dict__["_attrs"] = data

    @property
    def dict(self):
        return dict(self.__dict__.get("_attrs", {}))

    def __repr__(self):
        return f"<Event({self.type} {self.dict})>"


def post(ev):
    if ev is None:
        return False
    with _LOCK:
        _QUEUE.append(ev)
    return True


def get(eventtype=None):
    with _LOCK:
        if eventtype is None:
            items = list(_QUEUE)
            _QUEUE.clear()
            return items
        types = {eventtype} if isinstance(eventtype, int) else set(eventtype)
        matched = []
        kept = deque()
        for ev in _QUEUE:
            if ev.type in types:
                matched.append(ev)
            else:
                kept.append(ev)
        _QUEUE.clear()
        _QUEUE.extend(kept)
        return matched


def poll():
    with _LOCK:
        if _QUEUE:
            return _QUEUE.popleft()
    from . import locals as _L
    return Event(_L.NOEVENT)


def peek(eventtype=None):
    with _LOCK:
        if eventtype is None:
            return bool(_QUEUE)
        types = {eventtype} if isinstance(eventtype, int) else set(eventtype)
        return any(ev.type in types for ev in _QUEUE)


def clear(eventtype=None):
    with _LOCK:
        if eventtype is None:
            _QUEUE.clear()
            return
        types = {eventtype} if isinstance(eventtype, int) else set(eventtype)
        kept = deque(ev for ev in _QUEUE if ev.type not in types)
        _QUEUE.clear()
        _QUEUE.extend(kept)


def pump():
    return None
