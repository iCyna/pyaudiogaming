# -*- coding: utf-8 -*-
"""Cross-platform File Association, Launch URI Reader & Single-Instance IPC for PyAudioGaming.

Enables apps (such as music players or audio editors) to:
1. Register file extensions (e.g. ``.mp3``, ``.ogg``, ``.wav``) with the OS so pressing Enter /
   double-clicking a file launches your app directly (Windows HKCU Registry without Admin,
   Linux ``.desktop`` entry, and Android/macOS manifest snippets).
2. Read the file path or Android ``content://`` URI passed on launch (and resolve Android
   ``content://`` URIs to a readable local file for BASS ``sound.stream()``).
3. Enforce a **Single Instance** lock so opening a second file forwards its path to the
   already-running app window instead of spawning duplicate windows!
"""

import ctypes
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from . import system

__all__ = [
	"get_launch_files",
	"get_launch_file",
	"resolve_uri_to_file",
	"register_file_association",
	"unregister_file_association",
	"SingleInstance",
]


def get_launch_files(argv=None) -> list:
	"""Return a list of file paths or URIs passed to the application on launch."""
	if system.get_platform()["os"] == "android":
		act, _ = system.get_android_activity()
		if act is not None:
			try:
				intent = act.getIntent()
				if intent is not None:
					data_uri = intent.getData()
					if data_uri is not None:
						return [str(data_uri.toString())]
			except Exception:
				pass
		return []

	args = sys.argv[1:] if argv is None else list(argv)
	out = []
	for arg in args:
		s = str(arg).strip()
		if not s or s.startswith("-"):
			continue
		out.append(s)
	return out


def get_launch_file(argv=None):
	"""Return the first file path / URI passed on launch, or ``None``."""
	files = get_launch_files(argv=argv)
	return files[0] if files else None


def resolve_uri_to_file(path_or_uri: str, suffix: str = "") -> str:
	"""Convert an Android ``content://`` URI into a readable local temp file path.

	On Desktop (or regular filesystem paths), returns the path unchanged.
	"""
	s = str(path_or_uri or "").strip()
	if not s:
		return ""
	if not s.startswith("content://"):
		return s
	if system.get_platform()["os"] != "android":
		return s

	act, bridge = system.get_android_activity()
	if act is None:
		return s
	try:
		if bridge == "chaquopy":
			from java import jclass
			Uri = jclass("android.net.Uri")
		else:
			from jnius import autoclass
			Uri = autoclass("android.net.Uri")

		uri = Uri.parse(s)
		resolver = act.getContentResolver()
		stream = resolver.openInputStream(uri)
		if stream is None:
			return s
		try:
			out_dir = Path(os.environ.get("HOME") or tempfile.gettempdir()) / "pyag_opened"
			out_dir.mkdir(parents=True, exist_ok=True)
			digest = hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
			out_file = out_dir / f"opened_{digest}{suffix}"
			with open(out_file, "wb") as f:
				buf = bytearray(65536)
				while True:
					n = stream.read(buf)
					if n is None or n <= 0:
						break
					f.write(buf[:n])
			return str(out_file)
		finally:
			stream.close()
	except Exception:
		return s


def register_file_association(
	extensions,
	app_name: str,
	prog_id: str = None,
	exe_path: str = None,
	description: str = "",
	icon_path: str = None,
	mime_types=None,
) -> dict:
	"""Register file extensions so pressing Enter / double-clicking opens your app.

	- **Windows**: Registers under ``HKCU\\Software\\Classes`` (no Administrator privileges required!).
	- **Linux**: Writes ``~/.local/share/applications/<prog_id>.desktop`` and refreshes MIME database.
	- **Android / macOS / iOS**: Returns ready-to-use manifest / ``Info.plist`` snippet.
	"""
	exts = [("." + e.lstrip(".")).lower() for e in (extensions or ()) if str(e).strip()]
	if not exts:
		raise ValueError("Provide at least one file extension (e.g. ['.mp3', '.ogg'])")

	pid = prog_id or ("".join(c for c in app_name if c.isalnum()) + ".Document")
	desc = description or f"{app_name} File"

	if exe_path is None:
		if getattr(sys, "frozen", False):
			exe_cmd = f'"{sys.executable}" "%1"'
			exec_linux = f'"{sys.executable}" %f'
		else:
			script = os.path.abspath(sys.argv[0]) if sys.argv else ""
			exe_cmd = f'"{sys.executable}" "{script}" "%1"'
			exec_linux = f'"{sys.executable}" "{script}" %f'
	else:
		exe_cmd = f'"{os.path.abspath(exe_path)}" "%1"'
		exec_linux = f'"{os.path.abspath(exe_path)}" %f'

	# 1. Windows (HKCU — zero admin required)
	if os.name == "nt":
		import winreg
		for ext in exts:
			with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}") as k:
				winreg.SetValueEx(k, "", 0, winreg.REG_SZ, pid)
		with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{pid}") as k:
			winreg.SetValueEx(k, "", 0, winreg.REG_SZ, desc)
		with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{pid}\shell\open\command") as k:
			winreg.SetValueEx(k, "", 0, winreg.REG_SZ, exe_cmd)
		if icon_path:
			with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{pid}\DefaultIcon") as k:
				winreg.SetValueEx(k, "", 0, winreg.REG_SZ, str(icon_path))
		try:
			# Notify Windows Explorer of association change
			ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
		except Exception:
			pass
		return {"ok": True, "platform": "windows", "prog_id": pid, "extensions": exts}

	# 2. Linux (.desktop file)
	if system.get_platform()["os"] == "linux":
		apps_dir = Path.home() / ".local" / "share" / "applications"
		apps_dir.mkdir(parents=True, exist_ok=True)
		desktop_file = apps_dir / f"{pid.lower()}.desktop"
		mimes = ";".join(mime_types or ["audio/mpeg", "audio/ogg", "audio/wav", "audio/flac"]) + ";"
		content = (
			"[Desktop Entry]\n"
			"Type=Application\n"
			f"Name={app_name}\n"
			f"Comment={desc}\n"
			f"Exec={exec_linux}\n"
			f"MimeType={mimes}\n"
			"Terminal=false\n"
		)
		if icon_path:
			content += f"Icon={icon_path}\n"
		desktop_file.write_text(content, encoding="utf-8")
		if shutil.which("update-desktop-database"):
			try:
				subprocess.run(["update-desktop-database", str(apps_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			except Exception:
				pass
		return {"ok": True, "platform": "linux", "desktop_file": str(desktop_file), "extensions": exts}

	# 3. Android / macOS / iOS (declared at build time in Manifest / Info.plist)
	return {
		"ok": False,
		"platform": sys.platform,
		"note": "On Android/macOS/iOS, declare file associations in AndroidManifest.xml (ACTION_VIEW) or Info.plist (CFBundleDocumentTypes).",
		"extensions": exts,
	}


def unregister_file_association(extensions, prog_id: str) -> bool:
	"""Remove previously registered HKCU Windows or Linux .desktop file associations."""
	exts = [("." + e.lstrip(".")).lower() for e in (extensions or ()) if str(e).strip()]
	if os.name == "nt":
		import winreg
		for ext in exts:
			try:
				winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}")
			except OSError:
				pass
		for sub in (
			rf"Software\Classes\{prog_id}\shell\open\command",
			rf"Software\Classes\{prog_id}\shell\open",
			rf"Software\Classes\{prog_id}\shell",
			rf"Software\Classes\{prog_id}\DefaultIcon",
			rf"Software\Classes\{prog_id}",
		):
			try:
				winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
			except OSError:
				pass
		try:
			ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
		except Exception:
			pass
		return True

	if system.get_platform()["os"] == "linux":
		desktop_file = Path.home() / ".local" / "share" / "applications" / f"{prog_id.lower()}.desktop"
		if desktop_file.is_file():
			desktop_file.unlink()
			return True
	return False


class SingleInstance:
	"""Enforce a single running app instance and forward newly opened files to it.

	Usage::

		inst = SingleInstance("my_music_player")
		if not inst.is_primary:
			# Forwarded sys.argv[1:] to the already-running instance -> exit now!
			inst.send_args(get_launch_files())
			sys.exit(0)

		# Inside your main loop:
		for files in inst.poll():
			play_song(files[0])
	"""

	def __init__(self, app_id: str, port: int = None):
		self.app_id = str(app_id)
		if port is None:
			digest = int(hashlib.sha256(self.app_id.encode("utf-8")).hexdigest()[:4], 16)
			self.port = 41000 + (digest % 18000)
		else:
			self.port = int(port)

		self._sock = None
		self.is_primary = False
		self._try_acquire()

	def _try_acquire(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			s.bind(("127.0.0.1", self.port))
			s.listen(8)
			s.setblocking(False)
			self._sock = s
			self.is_primary = True
		except OSError:
			s.close()
			self._sock = None
			self.is_primary = False

	def send_args(self, args_list, timeout: float = 1.5) -> bool:
		"""Send a list of file paths / commands to the primary running instance."""
		payload = json.dumps({"app_id": self.app_id, "args": list(args_list or [])}).encode("utf-8")
		try:
			with socket.create_connection(("127.0.0.1", self.port), timeout=timeout) as conn:
				conn.sendall(payload)
			return True
		except OSError:
			return False

	def poll(self) -> list:
		"""Non-blocking check for messages forwarded by secondary instances. Call inside ``frameUpdate()``."""
		if not self.is_primary or self._sock is None:
			return []
		received = []
		while True:
			try:
				conn, _ = self._sock.accept()
			except BlockingIOError:
				break
			except OSError:
				break
			try:
				conn.settimeout(0.3)
				chunks = []
				while True:
					data = conn.recv(4096)
					if not data:
						break
					chunks.append(data)
				if chunks:
					msg = json.loads(b"".join(chunks).decode("utf-8"))
					if msg.get("app_id") == self.app_id:
						received.append(msg.get("args", []))
			except Exception:
				pass
			finally:
				conn.close()
		return received

	def close(self):
		if self._sock is not None:
			try:
				self._sock.close()
			except Exception:
				pass
			self._sock = None

	def __enter__(self) -> "SingleInstance":
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.close()
		return False
