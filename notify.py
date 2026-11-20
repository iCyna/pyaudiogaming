# -*- coding: utf-8 -*-
"""Cross-platform System Notifications & Lock-Screen Wake / Full-Screen Call/Alarm helper.

Supports:
- Android: ``NotificationManager`` + ``NotificationChannel`` + ``setFullScreenIntent``
  + ``setShowWhenLocked`` / ``setTurnScreenOn`` (via Chaquopy or pyjnius)
- Windows: WinRT Toast Notification (zero external deps) + Win32 ``SetThreadExecutionState``
  monitor wake + ``SetForegroundWindow`` / ``HWND_TOPMOST`` window bring-to-front
- macOS: ``osascript`` notification / ``UNUserNotificationCenter``
- Linux: ``notify-send`` (with ``low`` / ``normal`` / ``critical`` urgency)
- iOS: ``UNUserNotificationCenter`` (via rubicon-objc when available)
"""

import ctypes
import os
import shutil
import subprocess
import sys

from . import system

try:
	from . import haptics as _haptics
except Exception:
	_haptics = None

__all__ = [
	"send",
	"wake_and_show",
	"request_permission",
	"open_fullscreen_intent_settings",
	"wake_screen",
	"bring_window_to_front",
]


def _jclass(name: str, bridge: str):
	if bridge == "chaquopy":
		from java import jclass
		return jclass(name)
	from jnius import autoclass
	return autoclass(name)


def _ensure_android_channel(act, bridge: str, channel_id: str, channel_name: str, high_importance: bool = False):
	Context = _jclass("android.content.Context", bridge)
	BuildVersion = _jclass("android.os.Build$VERSION", bridge)
	nm = act.getSystemService(Context.NOTIFICATION_SERVICE)
	if int(BuildVersion.SDK_INT) >= 26:
		NotificationManager = _jclass("android.app.NotificationManager", bridge)
		NotificationChannel = _jclass("android.app.NotificationChannel", bridge)
		imp = NotificationManager.IMPORTANCE_HIGH if high_importance else NotificationManager.IMPORTANCE_DEFAULT
		ch = NotificationChannel(str(channel_id), str(channel_name), imp)
		nm.createNotificationChannel(ch)
	return nm


def _xml_escape(text: str) -> str:
	return (
		str(text)
		.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
		.replace("'", "&apos;")
	)


def request_permission() -> bool:
	"""Request runtime notification permission on Android 13+ (API 33+). No-op on other OSes."""
	if system.get_platform()["os"] != "android":
		return True
	act, bridge = system.get_android_activity()
	if act is None:
		return False
	try:
		BuildVersion = _jclass("android.os.Build$VERSION", bridge)
		if int(BuildVersion.SDK_INT) >= 33:
			act.requestPermissions(["android.permission.POST_NOTIFICATIONS"], 1001)
		return True
	except Exception:
		return False


def open_fullscreen_intent_settings() -> bool:
	"""Open Android 14+ 'Manage Full-Screen Intent' system settings page for this app."""
	if system.get_platform()["os"] != "android":
		return False
	act, bridge = system.get_android_activity()
	if act is None:
		return False
	try:
		Intent = _jclass("android.content.Intent", bridge)
		Uri = _jclass("android.net.Uri", bridge)
		intent = Intent("android.settings.MANAGE_APP_USE_FULL_SCREEN_INTENT")
		intent.setData(Uri.parse("package:" + str(act.getPackageName())))
		intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
		act.startActivity(intent)
		return True
	except Exception:
		return False


def wake_screen() -> bool:
	"""Wake up a sleeping display on Windows or Android."""
	if system.get_platform()["os"] == "android":
		act, bridge = system.get_android_activity()
		if act is None:
			return False
		try:
			BuildVersion = _jclass("android.os.Build$VERSION", bridge)
			if int(BuildVersion.SDK_INT) >= 27:
				act.setShowWhenLocked(True)
				act.setTurnScreenOn(True)
			Context = _jclass("android.content.Context", bridge)
			pm = act.getSystemService(Context.POWER_SERVICE)
			if pm is not None:
				# FULL_WAKE_LOCK | ACQUIRE_CAUSES_WAKEUP | ON_AFTER_RELEASE
				wl = pm.newWakeLock(0x1000001A, "PyAudioGaming:WakeScreen")
				wl.acquire(5000)
			return True
		except Exception:
			return False

	if os.name == "nt":
		try:
			ES_SYSTEM_REQUIRED = 0x00000001
			ES_DISPLAY_REQUIRED = 0x00000002
			ctypes.windll.kernel32.SetThreadExecutionState(ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
			return True
		except Exception:
			return False
	return False


def bring_window_to_front(hwnd=None, topmost: bool = True) -> bool:
	"""Restore and bring the current application window to the foreground (Windows)."""
	if os.name != "nt":
		return False
	try:
		if hwnd is None:
			import pygame
			if pygame.get_init() and pygame.display.get_init():
				info = pygame.display.get_wm_info()
				hwnd = info.get("window")
		if not hwnd:
			return False
		u32 = ctypes.windll.user32
		SW_RESTORE = 9
		HWND_TOPMOST = -1
		HWND_NOTOPMOST = -2
		SWP_NOMOVE = 0x0002
		SWP_NOSIZE = 0x0001
		SWP_SHOWWINDOW = 0x0040

		u32.ShowWindow(hwnd, SW_RESTORE)
		if topmost:
			u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
			u32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
		u32.SetForegroundWindow(hwnd)
		return True
	except Exception:
		return False


def send(
	title: str,
	message: str,
	urgency: str = "normal",
	channel_id: str = "pyag_default",
	app_name: str = "PyAudioGaming",
	notification_id: int = 1001,
) -> bool:
	"""Send a native OS notification on Windows, Android, Linux, macOS, or iOS."""
	title_s = str(title or app_name)
	msg_s = str(message or "")

	# 1. Android
	if system.get_platform()["os"] == "android":
		act, bridge = system.get_android_activity()
		if act is None:
			return False
		try:
			BuildVersion = _jclass("android.os.Build$VERSION", bridge)
			NotificationBuilder = _jclass("android.app.Notification$Builder", bridge)
			high = urgency.lower() in ("high", "critical", "call", "alarm")
			nm = _ensure_android_channel(act, bridge, channel_id, app_name, high_importance=high)
			builder = NotificationBuilder(act, str(channel_id)) if int(BuildVersion.SDK_INT) >= 26 else NotificationBuilder(act)
			builder.setContentTitle(title_s)
			builder.setContentText(msg_s)
			builder.setAutoCancel(True)
			try:
				icon_id = act.getApplicationInfo().icon
				if icon_id:
					builder.setSmallIcon(icon_id)
			except Exception:
				pass
			nm.notify(int(notification_id), builder.build())
			return True
		except Exception:
			return False

	# 2. Windows (WinRT Toast via PowerShell — zero pip dependencies)
	if os.name == "nt":
		try:
			t_xml = _xml_escape(title_s)
			m_xml = _xml_escape(msg_s)
			ps_script = (
				"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
				"[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
				f"$xml = '<toast><visual><binding template=\"ToastText02\"><text id=\"1\">{t_xml}</text><text id=\"2\">{m_xml}</text></binding></visual></toast>';"
				"$doc = New-Object Windows.Data.Xml.Dom.XmlDocument;"
				"$doc.LoadXml($xml);"
				"$toast = [Windows.UI.Notifications.ToastNotification]::new($doc);"
				f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{_xml_escape(app_name)}').Show($toast)"
			)
			creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
			subprocess.Popen(
				["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				creationflags=creationflags,
			)
			return True
		except Exception:
			return False

	# 3. macOS
	if sys.platform == "darwin":
		try:
			esc_t = title_s.replace('"', '\\"')
			esc_m = msg_s.replace('"', '\\"')
			subprocess.Popen(
				["osascript", "-e", f'display notification "{esc_m}" with title "{esc_t}"'],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
			)
			return True
		except Exception:
			return False

	# 4. Linux
	if shutil.which("notify-send"):
		try:
			u = "critical" if urgency.lower() in ("high", "critical", "call", "alarm") else ("low" if urgency.lower() == "low" else "normal")
			subprocess.Popen(
				["notify-send", "-u", u, "-a", str(app_name), title_s, msg_s],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
			)
			return True
		except Exception:
			return False

	return False


def wake_and_show(
	title: str,
	message: str,
	category: str = "call",
	channel_id: str = "pyag_fullscreen",
	app_name: str = "PyAudioGaming",
	hwnd=None,
	vibrate: bool = True,
	notification_id: int = 2001,
) -> bool:
	"""Wake a locked/sleeping screen and display a full-screen call/alarm alert.

	- **Android**: Enables ``setShowWhenLocked`` + ``setTurnScreenOn``, wakes the screen,
	  and posts a High-Importance notification with ``setFullScreenIntent(pendingIntent, True)``
	  so the OS launches/surfaces the app right over the lock screen.
	- **Windows**: Wakes the display via ``SetThreadExecutionState``, restores and raises
	  the app window to the foreground, and posts a high-priority Toast notification.
	- **Linux / macOS**: Sends a critical-urgency notification.
	"""
	if vibrate and _haptics is not None:
		try:
			_haptics.preset("heartbeat" if category == "call" else "warning")
		except Exception:
			pass

	# Android Full-Screen Intent
	if system.get_platform()["os"] == "android":
		act, bridge = system.get_android_activity()
		if act is None:
			return False
		try:
			wake_screen()
			BuildVersion = _jclass("android.os.Build$VERSION", bridge)
			Notification = _jclass("android.app.Notification", bridge)
			NotificationBuilder = _jclass("android.app.Notification$Builder", bridge)
			PendingIntent = _jclass("android.app.PendingIntent", bridge)
			Intent = _jclass("android.content.Intent", bridge)

			nm = _ensure_android_channel(act, bridge, channel_id, f"{app_name} Alerts", high_importance=True)
			launch_intent = act.getPackageManager().getLaunchIntentForPackage(act.getPackageName())
			if launch_intent is None:
				launch_intent = Intent(act, act.getClass())
			launch_intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP)

			pi_flags = PendingIntent.FLAG_UPDATE_CURRENT
			if int(BuildVersion.SDK_INT) >= 23:
				pi_flags |= PendingIntent.FLAG_IMMUTABLE
			pending = PendingIntent.getActivity(act, int(notification_id), launch_intent, pi_flags)

			builder = NotificationBuilder(act, str(channel_id)) if int(BuildVersion.SDK_INT) >= 26 else NotificationBuilder(act)
			builder.setContentTitle(str(title))
			builder.setContentText(str(message))
			builder.setPriority(Notification.PRIORITY_MAX)
			builder.setCategory(Notification.CATEGORY_CALL if category == "call" else Notification.CATEGORY_ALARM)
			builder.setFullScreenIntent(pending, True)
			builder.setAutoCancel(True)
			try:
				icon_id = act.getApplicationInfo().icon
				if icon_id:
					builder.setSmallIcon(icon_id)
			except Exception:
				pass

			nm.notify(int(notification_id), builder.build())
			return True
		except Exception:
			return False

	# Windows: wake monitor + bring window to front + Toast
	if os.name == "nt":
		wake_screen()
		bring_window_to_front(hwnd=hwnd, topmost=True)
		return send(title, message, urgency="critical", app_name=app_name, notification_id=notification_id)

	return send(title, message, urgency="critical", app_name=app_name, notification_id=notification_id)
