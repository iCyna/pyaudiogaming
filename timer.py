# -*- coding: utf-8 -*-
# Copyright 2026 belong ihcyna (Labubu) <phucnggo29@gmail.com>.
# High-precision game timer, cooldown, and frame scheduler.
# Supports Windows, Linux, macOS, Android, iOS, and Web.

import heapq
import time

__all__ = [
	"Timer",
	"Stopwatch",
	"CooldownManager",
	"TimerScheduler",
	"ScheduledTask",
	"FrameClock",
	"RateLimiter",
	"get_ticks",
	"get_ticks_us",
	"get_ticks_sec",
	"format_duration",
]

_EPOCH_NS = time.perf_counter_ns()


def get_ticks() -> int:
	"""Return monotonic milliseconds since module import (high-resolution, never jumps backwards)."""
	return (time.perf_counter_ns() - _EPOCH_NS) // 1_000_000


def get_ticks_us() -> int:
	"""Return monotonic microseconds since module import."""
	return (time.perf_counter_ns() - _EPOCH_NS) // 1_000


def get_ticks_sec() -> float:
	"""Return monotonic seconds (float) since module import."""
	return (time.perf_counter_ns() - _EPOCH_NS) / 1_000_000_000.0


def format_duration(ms: float, style: str = "clock") -> str:
	"""Format milliseconds into a human-readable string.

	Styles:
	- ``"clock"``: ``MM:SS`` or ``HH:MM:SS``
	- ``"clock_ms"``: ``MM:SS.mmm`` or ``HH:MM:SS.mmm``
	- ``"short"``: ``1h 2m 3s`` / ``450ms`` (screen-reader friendly)
	"""
	neg = ms < 0
	total_ms = abs(float(ms))
	sign = "-" if neg else ""

	if style == "short":
		if total_ms < 1000:
			return f"{sign}{int(round(total_ms))}ms"
		total_sec = int(total_ms // 1000)
		hours, rem = divmod(total_sec, 3600)
		minutes, seconds = divmod(rem, 60)
		parts = []
		if hours:
			parts.append(f"{hours}h")
		if minutes:
			parts.append(f"{minutes}m")
		if seconds or not parts:
			parts.append(f"{seconds}s")
		return sign + " ".join(parts)

	total_int_ms = int(total_ms)
	millis = total_int_ms % 1000
	total_sec = total_int_ms // 1000
	hours, rem = divmod(total_sec, 3600)
	minutes, seconds = divmod(rem, 60)

	if style == "clock_ms":
		if hours:
			return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
		return f"{sign}{minutes:02d}:{seconds:02d}.{millis:03d}"

	if hours:
		return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
	return f"{sign}{minutes:02d}:{seconds:02d}"


class Timer:
	"""High-precision game timer supporting pause/resume, time scaling, countdowns,
	fixed-interval ticks, forcing/advancing, serialization, and context-manager profiling.

	Backwards-compatible with::

		t = Timer()
		if t.elapsed >= 500:
			t.restart()
	"""

	__slots__ = ("_start_ns", "_accum_ns", "_paused", "_scale", "_duration_ms", "startTick")

	def __init__(self, duration: float = 0, paused: bool = False, scale: float = 1.0, auto_start: bool = True):
		if scale < 0:
			raise ValueError("Timer scale must be >= 0")
		self._duration_ms = max(0.0, float(duration))
		self._scale = float(scale)
		self._accum_ns = 0.0
		self._paused = bool(paused or not auto_start)
		now_ns = time.perf_counter_ns()
		self._start_ns = now_ns
		self.startTick = (now_ns - _EPOCH_NS) // 1_000_000

	def _raw_elapsed_ns(self) -> float:
		if self._paused:
			return self._accum_ns
		return self._accum_ns + (time.perf_counter_ns() - self._start_ns) * self._scale

	def _commit(self):
		now_ns = time.perf_counter_ns()
		if not self._paused:
			self._accum_ns += (now_ns - self._start_ns) * self._scale
		self._start_ns = now_ns
		return now_ns

	# ------------------------------------------------------------------
	# Core properties
	# ------------------------------------------------------------------
	@property
	def elapsed(self) -> int:
		"""Elapsed time in integer milliseconds (backwards-compatible)."""
		return int(self._raw_elapsed_ns() // 1_000_000)

	@elapsed.setter
	def elapsed(self, ms: float):
		self.force(ms)

	@property
	def elapsed_float(self) -> float:
		"""Elapsed time in floating-point milliseconds."""
		return self._raw_elapsed_ns() / 1_000_000.0

	@property
	def elapsed_us(self) -> int:
		"""Elapsed time in integer microseconds."""
		return int(self._raw_elapsed_ns() // 1_000)

	@property
	def elapsed_seconds(self) -> float:
		"""Elapsed time in seconds (float)."""
		return self._raw_elapsed_ns() / 1_000_000_000.0

	@property
	def paused(self) -> bool:
		return self._paused

	@property
	def running(self) -> bool:
		return not self._paused

	@property
	def scale(self) -> float:
		"""Time dilation factor (1.0 = normal, 0.5 = slow-mo, 2.0 = 2x speed)."""
		return self._scale

	@scale.setter
	def scale(self, value: float):
		value = float(value)
		if value < 0:
			raise ValueError("Timer scale must be >= 0")
		self._commit()
		self._scale = value

	@property
	def duration(self) -> float:
		"""Configured countdown duration in milliseconds (0 if none)."""
		return self._duration_ms

	@duration.setter
	def duration(self, ms: float):
		self._duration_ms = max(0.0, float(ms))

	@property
	def remaining(self) -> int:
		"""Remaining milliseconds until ``duration`` expires (clamped to >= 0)."""
		if self._duration_ms <= 0:
			return 0
		rem = self._duration_ms - self.elapsed_float
		return int(rem) if rem > 0 else 0

	@property
	def remaining_float(self) -> float:
		if self._duration_ms <= 0:
			return 0.0
		rem = self._duration_ms - self.elapsed_float
		return rem if rem > 0.0 else 0.0

	@property
	def remaining_seconds(self) -> float:
		return self.remaining_float / 1000.0

	@property
	def progress(self) -> float:
		"""Completion ratio from 0.0 to 1.0 when ``duration > 0``."""
		if self._duration_ms <= 0:
			return 1.0
		ratio = self.elapsed_float / self._duration_ms
		if ratio < 0.0:
			return 0.0
		if ratio > 1.0:
			return 1.0
		return ratio

	@property
	def expired(self) -> bool:
		"""True when ``duration > 0`` and elapsed >= duration."""
		return self._duration_ms > 0 and self.elapsed_float >= self._duration_ms

	done = expired
	finished = expired

	# ------------------------------------------------------------------
	# Control methods
	# ------------------------------------------------------------------
	def restart(self, duration: float = None, paused: bool = False):
		"""Reset elapsed time to 0 and start (unless ``paused=True``)."""
		if duration is not None:
			self._duration_ms = max(0.0, float(duration))
		now_ns = time.perf_counter_ns()
		self._accum_ns = 0.0
		self._start_ns = now_ns
		self._paused = bool(paused)
		self.startTick = (now_ns - _EPOCH_NS) // 1_000_000
		return self

	reset = restart

	def start(self, duration: float = None):
		"""Start or resume the timer. Optionally set a new duration and reset."""
		if duration is not None:
			return self.restart(duration=duration, paused=False)
		return self.resume()

	def pause(self):
		"""Freeze the timer at its current elapsed value."""
		if not self._paused:
			self._commit()
			self._paused = True
		return self

	def resume(self):
		"""Resume a paused timer from where it left off."""
		if self._paused:
			self._start_ns = time.perf_counter_ns()
			self._paused = False
		return self

	def toggle_pause(self) -> bool:
		"""Toggle paused state and return the new ``paused`` boolean."""
		if self._paused:
			self.resume()
		else:
			self.pause()
		return self._paused

	def stop(self):
		"""Stop and reset elapsed time to 0."""
		return self.restart(paused=True)

	def force(self, ms: float):
		"""Force the timer's elapsed time to a specific millisecond value (like BGT ``timer.force``)."""
		now_ns = time.perf_counter_ns()
		self._accum_ns = float(ms) * 1_000_000.0
		self._start_ns = now_ns
		self.startTick = int((now_ns - _EPOCH_NS - self._accum_ns) // 1_000_000)
		return self

	def advance(self, delta_ms: float):
		"""Add ``delta_ms`` milliseconds to the current elapsed time."""
		self._commit()
		self._accum_ns += float(delta_ms) * 1_000_000.0
		return self

	def rewind(self, delta_ms: float, clamp_zero: bool = True):
		"""Subtract ``delta_ms`` milliseconds from the current elapsed time."""
		self._commit()
		self._accum_ns -= float(delta_ms) * 1_000_000.0
		if clamp_zero and self._accum_ns < 0.0:
			self._accum_ns = 0.0
		return self

	# ------------------------------------------------------------------
	# Game-loop & cooldown helpers
	# ------------------------------------------------------------------
	def ready(self, cooldown_ms: float = None, auto_restart: bool = False) -> bool:
		"""Check whether ``cooldown_ms`` (or ``self.duration``) has elapsed.

		If ``auto_restart=True`` and ready, restarts the timer automatically.
		"""
		limit = self._duration_ms if cooldown_ms is None else float(cooldown_ms)
		if self.elapsed_float >= limit:
			if auto_restart:
				self.restart()
			return True
		return False

	def consume(self, interval_ms: float = None) -> bool:
		"""Drift-free periodic trigger: if ``elapsed >= interval``, subtracts one interval
		(preserving sub-millisecond remainder) and returns ``True``.
		"""
		interval = self._duration_ms if interval_ms is None else float(interval_ms)
		if interval <= 0:
			return False
		self._commit()
		interval_ns = interval * 1_000_000.0
		if self._accum_ns >= interval_ns:
			self._accum_ns -= interval_ns
			return True
		return False

	def consume_all(self, interval_ms: float = None, max_ticks: int = None) -> int:
		"""Consume all completed intervals and return how many occurred (drift-free)."""
		interval = self._duration_ms if interval_ms is None else float(interval_ms)
		if interval <= 0:
			return 0
		self._commit()
		interval_ns = interval * 1_000_000.0
		if self._accum_ns < interval_ns:
			return 0
		count = int(self._accum_ns // interval_ns)
		if max_ticks is not None and count > max_ticks:
			count = max_ticks
			self._accum_ns = 0.0
		else:
			self._accum_ns -= count * interval_ns
		return count

	def format(self, style: str = "clock", remaining: bool = False) -> str:
		"""Format either elapsed or remaining time using ``format_duration``."""
		val = self.remaining_float if remaining else self.elapsed_float
		return format_duration(val, style=style)

	# ------------------------------------------------------------------
	# Serialization
	# ------------------------------------------------------------------
	def to_dict(self) -> dict:
		return {
			"elapsed_ms": self.elapsed_float,
			"duration_ms": self._duration_ms,
			"paused": self._paused,
			"scale": self._scale,
		}

	@classmethod
	def from_dict(cls, data: dict) -> "Timer":
		t = cls(
			duration=data.get("duration_ms", 0.0),
			paused=bool(data.get("paused", False)),
			scale=float(data.get("scale", 1.0)),
		)
		t.force(float(data.get("elapsed_ms", 0.0)))
		return t

	# ------------------------------------------------------------------
	# Context manager & Python dunder methods
	# ------------------------------------------------------------------
	def __enter__(self) -> "Timer":
		self.restart()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.pause()
		return False

	def __int__(self) -> int:
		return self.elapsed

	def __float__(self) -> float:
		return self.elapsed_float

	def __bool__(self) -> bool:
		return not self._paused

	def __lt__(self, other):
		if isinstance(other, Timer):
			return self.elapsed_float < other.elapsed_float
		if isinstance(other, (int, float)):
			return self.elapsed_float < other
		return NotImplemented

	def __le__(self, other):
		if isinstance(other, Timer):
			return self.elapsed_float <= other.elapsed_float
		if isinstance(other, (int, float)):
			return self.elapsed_float <= other
		return NotImplemented

	def __gt__(self, other):
		if isinstance(other, Timer):
			return self.elapsed_float > other.elapsed_float
		if isinstance(other, (int, float)):
			return self.elapsed_float > other
		return NotImplemented

	def __ge__(self, other):
		if isinstance(other, Timer):
			return self.elapsed_float >= other.elapsed_float
		if isinstance(other, (int, float)):
			return self.elapsed_float >= other
		return NotImplemented

	def __repr__(self) -> str:
		state = "paused" if self._paused else "running"
		if self._duration_ms > 0:
			return f"Timer(elapsed={self.elapsed}ms, duration={int(self._duration_ms)}ms, {state}, scale={self._scale})"
		return f"Timer(elapsed={self.elapsed}ms, {state}, scale={self._scale})"


class Stopwatch(Timer):
	"""Timer with lap recording for profiling and split timing."""

	def __init__(self, auto_start: bool = True):
		super().__init__(auto_start=auto_start)
		self._laps = []
		self._last_lap_ms = 0.0

	def restart(self, duration: float = None, paused: bool = False):
		self._laps = []
		self._last_lap_ms = 0.0
		return super().restart(duration=duration, paused=paused)

	def lap(self, label: str = "") -> dict:
		"""Record a lap split and return ``{"index", "label", "split_ms", "total_ms"}``."""
		total = self.elapsed_float
		split = total - self._last_lap_ms
		self._last_lap_ms = total
		entry = {
			"index": len(self._laps) + 1,
			"label": label or f"Lap {len(self._laps) + 1}",
			"split_ms": split,
			"total_ms": total,
		}
		self._laps.append(entry)
		return entry

	@property
	def laps(self) -> list:
		return list(self._laps)

	@property
	def last_lap(self):
		return self._laps[-1] if self._laps else None

	def summary(self) -> str:
		lines = [f"Total: {format_duration(self.elapsed_float, 'clock_ms')}"]
		for item in self._laps:
			lines.append(
				f"  #{item['index']} {item['label']}: +{item['split_ms']:.2f}ms (total {item['total_ms']:.2f}ms)"
			)
		return "\n".join(lines)


class CooldownManager:
	"""Manage named cooldowns (skills, attacks, actions, anti-spam) in one place."""

	def __init__(self, scale: float = 1.0):
		self._timers = {}
		self._scale = max(0.0, float(scale))
		self._paused = False

	def start(self, name: str, duration_ms: float) -> Timer:
		t = Timer(duration=duration_ms, paused=self._paused, scale=self._scale)
		self._timers[name] = t
		return t

	def is_ready(self, name: str) -> bool:
		t = self._timers.get(name)
		if t is None:
			return True
		return t.expired

	def use(self, name: str, duration_ms: float) -> bool:
		"""If ``name`` is ready, start its cooldown and return ``True``; otherwise ``False``."""
		if not self.is_ready(name):
			return False
		self.start(name, duration_ms)
		return True

	def remaining(self, name: str) -> int:
		t = self._timers.get(name)
		return 0 if t is None else t.remaining

	def remaining_seconds(self, name: str) -> float:
		t = self._timers.get(name)
		return 0.0 if t is None else t.remaining_seconds

	def progress(self, name: str) -> float:
		t = self._timers.get(name)
		return 1.0 if t is None else t.progress

	def reduce(self, name: str, delta_ms: float):
		t = self._timers.get(name)
		if t is not None:
			t.advance(delta_ms)

	def reduce_all(self, delta_ms: float):
		for t in self._timers.values():
			t.advance(delta_ms)

	def reset(self, name: str):
		self._timers.pop(name, None)

	def clear(self):
		self._timers.clear()

	def pause_all(self):
		self._paused = True
		for t in self._timers.values():
			t.pause()

	def resume_all(self):
		self._paused = False
		for t in self._timers.values():
			t.resume()

	def set_scale(self, scale: float):
		self._scale = max(0.0, float(scale))
		for t in self._timers.values():
			t.scale = self._scale

	def active(self) -> list:
		"""Return names of cooldowns that have not expired yet."""
		return [k for k, t in self._timers.items() if not t.expired]

	def prune(self):
		"""Remove expired cooldown entries to keep memory clean."""
		for k in [k for k, t in self._timers.items() if t.expired]:
			del self._timers[k]

	def to_dict(self) -> dict:
		return {
			"scale": self._scale,
			"paused": self._paused,
			"timers": {k: t.to_dict() for k, t in self._timers.items() if not t.expired},
		}

	@classmethod
	def from_dict(cls, data: dict) -> "CooldownManager":
		mgr = cls(scale=float(data.get("scale", 1.0)))
		mgr._paused = bool(data.get("paused", False))
		for k, v in (data.get("timers") or {}).items():
			mgr._timers[k] = Timer.from_dict(v)
		return mgr


class ScheduledTask:
	"""Handle representing a task scheduled in ``TimerScheduler``."""

	__slots__ = (
		"task_id", "callback", "args", "kwargs", "interval_ms",
		"repeat", "remaining_runs", "due_ms", "cancelled", "paused", "_paused_rem_ms", "tag"
	)

	def __init__(self, task_id, callback, args, kwargs, delay_ms, interval_ms=0.0, count=1, due_ms=0.0, tag=None):
		self.task_id = task_id
		self.callback = callback
		self.args = args
		self.kwargs = kwargs
		self.interval_ms = float(interval_ms)
		self.repeat = interval_ms > 0
		self.remaining_runs = count  # None means infinite
		self.due_ms = float(due_ms)
		self.cancelled = False
		self.paused = False
		self._paused_rem_ms = 0.0
		self.tag = tag

	def cancel(self):
		self.cancelled = True


class TimerScheduler:
	"""Non-blocking, min-heap event scheduler designed for game loops.

	Call ``scheduler.update()`` each frame. Supports one-shot (``after``),
	repeating (``every``), pause/resume, time scaling, tags, and cancellation.
	"""

	def __init__(self, scale: float = 1.0, on_error=None):
		self._clock = Timer(scale=scale)
		self._heap = []
		self._tasks = {}
		self._next_id = 1
		self._on_error = on_error

	@property
	def now_ms(self) -> float:
		return self._clock.elapsed_float

	@property
	def scale(self) -> float:
		return self._clock.scale

	@scale.setter
	def scale(self, value: float):
		self._clock.scale = value

	@property
	def paused(self) -> bool:
		return self._clock.paused

	def pause_all(self):
		self._clock.pause()

	def resume_all(self):
		self._clock.resume()

	def after(self, delay_ms: float, callback, *args, tag=None, **kwargs) -> int:
		"""Schedule ``callback(*args, **kwargs)`` once after ``delay_ms`` milliseconds."""
		tid = self._next_id
		self._next_id += 1
		due = self.now_ms + max(0.0, float(delay_ms))
		task = ScheduledTask(tid, callback, args, kwargs, delay_ms, interval_ms=0.0, count=1, due_ms=due, tag=tag)
		self._tasks[tid] = task
		heapq.heappush(self._heap, (due, tid))
		return tid

	def every(self, interval_ms: float, callback, *args, count: int = None, start_immediately: bool = False, tag=None, **kwargs) -> int:
		"""Schedule ``callback`` repeatedly every ``interval_ms`` (optionally ``count`` times)."""
		interval_ms = float(interval_ms)
		if interval_ms <= 0:
			raise ValueError("interval_ms must be > 0")
		tid = self._next_id
		self._next_id += 1
		due = self.now_ms if start_immediately else (self.now_ms + interval_ms)
		task = ScheduledTask(tid, callback, args, kwargs, interval_ms, interval_ms=interval_ms, count=count, due_ms=due, tag=tag)
		self._tasks[tid] = task
		heapq.heappush(self._heap, (due, tid))
		return tid

	def cancel(self, task_id: int) -> bool:
		task = self._tasks.pop(task_id, None)
		if task is None:
			return False
		task.cancelled = True
		return True

	def cancel_by_tag(self, tag) -> int:
		to_cancel = [tid for tid, t in self._tasks.items() if t.tag == tag]
		for tid in to_cancel:
			self._tasks[tid].cancelled = True
			del self._tasks[tid]
		return len(to_cancel)

	def pause_task(self, task_id: int) -> bool:
		task = self._tasks.get(task_id)
		if task is None or task.paused or task.cancelled:
			return False
		task.paused = True
		task._paused_rem_ms = max(0.0, task.due_ms - self.now_ms)
		return True

	def resume_task(self, task_id: int) -> bool:
		task = self._tasks.get(task_id)
		if task is None or not task.paused or task.cancelled:
			return False
		task.paused = False
		task.due_ms = self.now_ms + task._paused_rem_ms
		heapq.heappush(self._heap, (task.due_ms, task.task_id))
		return True

	def clear(self):
		for t in self._tasks.values():
			t.cancelled = True
		self._tasks.clear()
		self._heap.clear()

	def pending_count(self) -> int:
		return len(self._tasks)

	def next_due_ms(self):
		"""Milliseconds until next active task fires, or ``None`` if queue is empty."""
		now = self.now_ms
		while self._heap:
			due, tid = self._heap[0]
			task = self._tasks.get(tid)
			if task is None or task.cancelled or task.paused or due != task.due_ms:
				heapq.heappop(self._heap)
				continue
			return max(0.0, due - now)
		return None

	def update(self, max_callbacks: int = 64) -> int:
		"""Run all due callbacks. Returns the number of callbacks executed."""
		if self._clock.paused:
			return 0
		executed = 0
		while executed < max_callbacks:
			now = self.now_ms
			task = None
			while self._heap:
				due, tid = self._heap[0]
				cand = self._tasks.get(tid)
				if cand is None or cand.cancelled or cand.paused or due != cand.due_ms:
					heapq.heappop(self._heap)
					continue
				if due > now:
					break
				heapq.heappop(self._heap)
				task = cand
				break
			if task is None:
				break

			if task.repeat and (task.remaining_runs is None or task.remaining_runs > 1):
				if task.remaining_runs is not None:
					task.remaining_runs -= 1
				# Advance without drift, but don't spiral if game stalled
				next_due = task.due_ms + task.interval_ms
				if next_due < now:
					next_due = now + task.interval_ms
				task.due_ms = next_due
				heapq.heappush(self._heap, (task.due_ms, task.task_id))
			else:
				self._tasks.pop(task.task_id, None)

			try:
				task.callback(*task.args, **task.kwargs)
			except Exception as exc:
				if self._on_error:
					self._on_error(exc, task)
				else:
					raise
			executed += 1
		return executed


class FrameClock:
	"""Game-loop clock providing delta time, smoothed FPS, frame limiting, and fixed timesteps."""

	def __init__(self, target_fps: float = 0.0, max_dt_ms: float = 100.0):
		self.target_fps = max(0.0, float(target_fps))
		self.max_dt_ms = max(1.0, float(max_dt_ms))
		self._last_ns = time.perf_counter_ns()
		self._dt_ms = 0.0
		self._fps = 0.0
		self._frame_count = 0
		self._accumulator_ms = 0.0

	def tick(self, target_fps: float = None) -> float:
		"""Advance one frame, sleep if ``target_fps > 0``, and return delta time in **seconds**."""
		fps_limit = self.target_fps if target_fps is None else max(0.0, float(target_fps))
		if fps_limit > 0.0:
			frame_budget_ns = int(1_000_000_000.0 / fps_limit)
			target_ns = self._last_ns + frame_budget_ns
			now_ns = time.perf_counter_ns()
			rem_ns = target_ns - now_ns
			if rem_ns > 2_000_000:
				time.sleep((rem_ns - 1_500_000) / 1_000_000_000.0)
			while time.perf_counter_ns() < target_ns:
				pass

		now_ns = time.perf_counter_ns()
		raw_ms = (now_ns - self._last_ns) / 1_000_000.0
		self._last_ns = now_ns

		self._dt_ms = min(raw_ms, self.max_dt_ms)
		self._frame_count += 1
		self._accumulator_ms += self._dt_ms

		inst_fps = (1000.0 / raw_ms) if raw_ms > 0.0 else 0.0
		if self._fps <= 0.0:
			self._fps = inst_fps
		else:
			self._fps = self._fps * 0.9 + inst_fps * 0.1

		return self._dt_ms / 1000.0

	def fixed_steps(self, step_ms: float = 16.6666667, max_steps: int = 5):
		"""Yield fixed-timestep ``dt`` (seconds) to keep physics/movement deterministic."""
		step_ms = max(0.1, float(step_ms))
		step_sec = step_ms / 1000.0
		steps = 0
		while self._accumulator_ms >= step_ms and steps < max_steps:
			self._accumulator_ms -= step_ms
			steps += 1
			yield step_sec
		if steps >= max_steps and self._accumulator_ms > step_ms * max_steps:
			self._accumulator_ms = 0.0

	@property
	def dt(self) -> float:
		"""Last frame delta time in seconds."""
		return self._dt_ms / 1000.0

	@property
	def dt_ms(self) -> float:
		"""Last frame delta time in milliseconds."""
		return self._dt_ms

	@property
	def fps(self) -> float:
		"""Exponentially smoothed FPS."""
		return self._fps

	@property
	def frame_count(self) -> int:
		return self._frame_count


class RateLimiter:
	"""Token-bucket rate limiter for network packets, chat anti-spam, or TTS throttling."""

	def __init__(self, max_calls: int, per_ms: float):
		if max_calls <= 0 or per_ms <= 0:
			raise ValueError("max_calls and per_ms must be > 0")
		self.max_calls = float(max_calls)
		self.per_ms = float(per_ms)
		self._tokens = float(max_calls)
		self._timer = Timer()

	def _refill(self):
		elapsed = self._timer.elapsed_float
		if elapsed > 0:
			self._timer.restart()
			self._tokens = min(self.max_calls, self._tokens + elapsed * (self.max_calls / self.per_ms))

	def allow(self, cost: float = 1.0) -> bool:
		"""Return ``True`` and consume ``cost`` tokens if allowed, else ``False``."""
		self._refill()
		if self._tokens >= cost:
			self._tokens -= cost
			return True
		return False

	def retry_after_ms(self, cost: float = 1.0) -> float:
		"""Milliseconds until ``cost`` tokens will be available."""
		self._refill()
		if self._tokens >= cost:
			return 0.0
		needed = cost - self._tokens
		return needed * (self.per_ms / self.max_calls)

	def reset(self):
		self._tokens = self.max_calls
		self._timer.restart()
