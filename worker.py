# -*- coding: utf-8 -*-
"""Cross-platform background task & shared-state runner for PyAudioGaming.

Automatically adapts to every platform with one unified API:
- Windows / Linux / macOS: supports ``process`` (true multi-core CPU parallelism),
  ``thread`` (zero-overhead I/O & C-extension parallelism), and ``inline``.
- Android / iOS: automatically falls back from ``process`` to ``thread`` because
  mobile sandboxes restrict ``multiprocessing`` / ``sem_open``.
- Web (Pyodide / Emscripten): automatically falls back to ``inline`` so apps never
  crash with ``NotImplementedError``.

Callbacks (``on_done``, ``on_error``) are always delivered safely on the **main game
thread** when you call ``pool.poll()`` inside your game loop.
"""

from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing
import os
import pickle
import sys
import threading

from . import system
from .timer import Timer

__all__ = [
	"TaskPool",
	"TaskHandle",
	"SharedState",
	"detect_best_mode",
	"enable_freeze_support",
]

_FREEZE_SUPPORT_CALLED = False


def enable_freeze_support():
	"""Safely call ``multiprocessing.freeze_support()`` once (prevents fork-bomb in PyInstaller/Nuitka)."""
	global _FREEZE_SUPPORT_CALLED
	if not _FREEZE_SUPPORT_CALLED:
		_FREEZE_SUPPORT_CALLED = True
		try:
			multiprocessing.freeze_support()
		except Exception:
			pass


def _supports_multiprocessing() -> bool:
	if system.get_platform()["os"] in ("android", "ios", "web"):
		return False
	try:
		ctx = multiprocessing.get_context()
		q = ctx.Queue()
		q.close()
		return True
	except Exception:
		return False


def detect_best_mode(preferred: str = "auto") -> str:
	"""Resolve requested execution mode (``'auto'``, ``'process'``, ``'thread'``, ``'inline'``)
	to a mode guaranteed to work on the current OS.
	"""
	pref = (preferred or "auto").lower().strip()
	os_name = system.get_platform()["os"]
	if pref == "inline" or os_name == "web":
		return "inline"
	if pref == "thread":
		return "thread"
	if pref == "process":
		return "process" if _supports_multiprocessing() else "thread"
	if os_name in ("android", "ios"):
		return "thread"
	return "process" if _supports_multiprocessing() else "thread"


def _is_picklable(fn, args, kwargs) -> bool:
	try:
		pickle.dumps((fn, args, kwargs))
		return True
	except Exception:
		return False


class SharedState:
	"""Simple dict-like shared state that works across ``process``, ``thread``, and ``inline`` modes.

	Example::

		state = SharedState(mode="auto", initial={"loaded": 0, "total": 100})
		state["loaded"] = 25
		snap = state.snapshot()
	"""

	def __init__(self, mode: str = "auto", initial: dict = None):
		self.mode = detect_best_mode(mode)
		self._manager = None
		self._lock = threading.RLock() if self.mode == "thread" else None
		if self.mode == "process":
			enable_freeze_support()
			try:
				self._manager = multiprocessing.Manager()
				self._store = self._manager.dict(initial or {})
			except Exception:
				self.mode = "thread"
				self._lock = threading.RLock()
				self._store = dict(initial or {})
		else:
			self._store = dict(initial or {})

	@property
	def raw(self):
		"""Underlying dict / DictProxy (pass this into worker functions in ``process`` mode)."""
		return self._store

	def get(self, key, default=None):
		if self._lock:
			with self._lock:
				return self._store.get(key, default)
		return self._store.get(key, default)

	def set(self, key, value):
		if self._lock:
			with self._lock:
				self._store[key] = value
		else:
			self._store[key] = value

	def update(self, mapping: dict):
		if self._lock:
			with self._lock:
				self._store.update(mapping)
		else:
			self._store.update(mapping)

	def pop(self, key, default=None):
		if self._lock:
			with self._lock:
				return self._store.pop(key, default)
		return self._store.pop(key, default)

	def clear(self):
		if self._lock:
			with self._lock:
				self._store.clear()
		else:
			self._store.clear()

	def snapshot(self) -> dict:
		"""Return a plain local ``dict`` copy of the current state."""
		if self._lock:
			with self._lock:
				return dict(self._store)
		return dict(self._store)

	def close(self):
		if self._manager is not None:
			try:
				self._manager.shutdown()
			except Exception:
				pass
			self._manager = None

	def __getitem__(self, key):
		if self._lock:
			with self._lock:
				return self._store[key]
		return self._store[key]

	def __setitem__(self, key, value):
		self.set(key, value)

	def __contains__(self, key) -> bool:
		if self._lock:
			with self._lock:
				return key in self._store
		return key in self._store

	def __len__(self) -> int:
		if self._lock:
			with self._lock:
				return len(self._store)
		return len(self._store)


class TaskHandle:
	"""Handle returned by ``TaskPool.submit()`` to track status, result, or cancel."""

	__slots__ = (
		"task_id", "tag", "_future", "_timer", "_on_done", "_on_error",
		"_dispatched", "_inline_fn", "_inline_args", "_inline_kwargs",
		"_inline_done", "_inline_cancelled", "_inline_result", "_inline_error",
	)

	def __init__(self, task_id: int, future=None, on_done=None, on_error=None, tag=None):
		self.task_id = task_id
		self.tag = tag
		self._future = future
		self._timer = Timer()
		self._on_done = on_done
		self._on_error = on_error
		self._dispatched = False
		self._inline_fn = None
		self._inline_args = ()
		self._inline_kwargs = {}
		self._inline_done = False
		self._inline_cancelled = False
		self._inline_result = None
		self._inline_error = None

	@property
	def done(self) -> bool:
		if self._future is not None:
			return self._future.done()
		return self._inline_done or self._inline_cancelled

	@property
	def cancelled(self) -> bool:
		if self._future is not None:
			return self._future.cancelled()
		return self._inline_cancelled

	@property
	def running(self) -> bool:
		return not self.done

	@property
	def elapsed_ms(self) -> int:
		return self._timer.elapsed

	@property
	def error(self):
		if self._future is not None:
			if self._future.done() and not self._future.cancelled():
				return self._future.exception()
			return None
		return self._inline_error

	def result(self, timeout=None):
		if self._future is not None:
			return self._future.result(timeout=timeout)
		if self._inline_error is not None:
			raise self._inline_error
		return self._inline_result

	def cancel(self) -> bool:
		if self._future is not None:
			return self._future.cancel()
		if not self._inline_done:
			self._inline_cancelled = True
			return True
		return False


class TaskPool:
	"""Cross-platform background worker pool with main-thread callback polling.

	Example::

		pool = TaskPool(mode="auto")
		pool.submit(heavy_map_gen, seed=42, on_done=lambda m: print("Map ready:", m))
		# Inside game loop:
		pool.poll()
	"""

	def __init__(self, mode: str = "auto", max_workers: int = None):
		self.mode = detect_best_mode(mode)
		cpu = os.cpu_count() or 2
		self.max_workers = max(1, int(max_workers or min(4, cpu)))
		self._proc_pool = None
		self._thread_pool = None
		self._handles = []
		self._next_id = 1
		self._closed = False

		if self.mode == "process":
			enable_freeze_support()

	def _get_proc_pool(self):
		if self._proc_pool is None:
			self._proc_pool = ProcessPoolExecutor(max_workers=self.max_workers)
		return self._proc_pool

	def _get_thread_pool(self):
		if self._thread_pool is None:
			self._thread_pool = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="pyag_worker")
		return self._thread_pool

	def submit(self, fn, *args, on_done=None, on_error=None, tag=None, prefer_thread: bool = False, **kwargs) -> TaskHandle:
		"""Submit a callable for execution and return a ``TaskHandle``.

		In ``process`` mode, if ``fn`` is a lambda/closure that cannot be pickled,
		it automatically falls back to ``thread`` mode instead of raising ``PicklingError``.
		"""
		if self._closed:
			raise RuntimeError("TaskPool has been shut down")

		tid = self._next_id
		self._next_id += 1

		if self.mode == "inline":
			handle = TaskHandle(tid, future=None, on_done=on_done, on_error=on_error, tag=tag)
			handle._inline_fn = fn
			handle._inline_args = args
			handle._inline_kwargs = kwargs
			self._handles.append(handle)
			return handle

		use_proc = (self.mode == "process") and not prefer_thread and _is_picklable(fn, args, kwargs)
		if use_proc:
			try:
				fut = self._get_proc_pool().submit(fn, *args, **kwargs)
			except Exception:
				fut = self._get_thread_pool().submit(fn, *args, **kwargs)
		else:
			fut = self._get_thread_pool().submit(fn, *args, **kwargs)

		handle = TaskHandle(tid, future=fut, on_done=on_done, on_error=on_error, tag=tag)
		self._handles.append(handle)
		return handle

	def map_async(self, fn, items, on_done=None, on_error=None, tag=None, prefer_thread: bool = False) -> list:
		"""Submit ``fn(item)`` for each item in ``items`` and return the list of ``TaskHandle`` objects."""
		return [
			self.submit(fn, item, on_done=on_done, on_error=on_error, tag=tag, prefer_thread=prefer_thread)
			for item in items
		]

	def poll(self, max_callbacks: int = 32) -> int:
		"""Dispatch completed task callbacks on the **main thread** (call inside ``frameUpdate()``).

		In ``inline`` mode, executes up to ``max_callbacks`` queued jobs per poll.
		Returns the number of completed jobs dispatched.
		"""
		dispatched = 0
		remaining = []

		for h in self._handles:
			if dispatched >= max_callbacks:
				remaining.append(h)
				continue

			# Inline mode execution
			if h._future is None and not h._inline_done and not h._inline_cancelled:
				try:
					h._inline_result = h._inline_fn(*h._inline_args, **h._inline_kwargs)
				except Exception as exc:
					h._inline_error = exc
				h._inline_done = True
				h._timer.pause()

			if not h.done:
				remaining.append(h)
				continue

			h._timer.pause()
			if not h._dispatched and not h.cancelled:
				h._dispatched = True
				err = h.error
				if err is not None:
					if h._on_error:
						h._on_error(err)
				elif h._on_done:
					h._on_done(h.result())
				dispatched += 1

		self._handles = remaining
		return dispatched

	def wait(self, handle: TaskHandle, timeout=None):
		"""Block until ``handle`` completes and return its result."""
		if handle._future is None and not handle._inline_done and not handle._inline_cancelled:
			try:
				handle._inline_result = handle._inline_fn(*handle._inline_args, **handle._inline_kwargs)
			except Exception as exc:
				handle._inline_error = exc
			handle._inline_done = True
			handle._timer.pause()
		res = handle.result(timeout=timeout)
		self.poll()
		return res

	def pending_count(self) -> int:
		return sum(1 for h in self._handles if not h.done)

	def cancel_by_tag(self, tag) -> int:
		count = 0
		for h in self._handles:
			if h.tag == tag and h.cancel():
				count += 1
		return count

	def shutdown(self, wait: bool = False):
		self._closed = True
		for h in self._handles:
			h.cancel()
		self._handles.clear()
		if self._proc_pool is not None:
			self._proc_pool.shutdown(wait=wait, cancel_futures=True)
			self._proc_pool = None
		if self._thread_pool is not None:
			self._thread_pool.shutdown(wait=wait, cancel_futures=True)
			self._thread_pool = None

	def __enter__(self) -> "TaskPool":
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.shutdown(wait=True)
		return False
