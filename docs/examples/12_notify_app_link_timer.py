# -*- coding: utf-8 -*-
"""Example 12: System Notifications, File Associations (app_link), InputBox & Precision Timers."""
import time
from pyaudiogaming import notify, app_link
from pyaudiogaming.timer import Timer, CooldownManager, TimerScheduler


def main():
    # 1. High-precision Timer, CooldownManager, and TimerScheduler (works headless)
    t = Timer()
    cd = CooldownManager()
    sched = TimerScheduler()
    sched.after(150, lambda: print(f"Scheduled event fired at {t.elapsed} ms!"))

    if cd.use("ping", 1000):
        print("Cooldown 'ping' started, remaining:", round(cd.remaining_seconds("ping"), 2), "s")

    for _ in range(25):
        sched.update()
        time.sleep(0.01)

    # 2. Launch URI / file-open argument reader
    print("Launch URI/path:", app_link.get_launch_uri())

    # 3. System notification (Windows Toast / Android Notification / macOS / Linux)
    notify.send("PyAudioGaming", "Background task completed!")


if __name__ == "__main__":
    main()
