# -*- coding: utf-8 -*-
"""Example 02 (Intermediate): InputMap + Haptics + CooldownManager + TimerScheduler."""
from pyaudiogaming.window import Window
from pyaudiogaming.input_map import InputMap
from pyaudiogaming.timer import CooldownManager, TimerScheduler
from pyaudiogaming import haptics


def main():
    wnd = Window()
    wnd.init(800, 600, "InputMap & Haptics Demo")
    imap = InputMap({"attack": ["space", "tap:1:2", "pad:a"], "quit": ["escape", "swipe:left:2", "pad:back"]})
    cd = CooldownManager()
    sched = TimerScheduler()
    wnd.say("Press " + imap.describe("attack") + " to attack, Escape to quit.")
    while True:
        wnd.frameUpdate()
        haptics.update()
        sched.update()
        if imap.pressed("attack", wnd):
            if cd.use("attack", 1500):
                haptics.preset("hit_heavy")
                wnd.say("Direct hit!")
                sched.after(1500, lambda: wnd.say("Attack ready!"))
            else:
                haptics.preset("blocked")
                wnd.say(f"Cooldown: {cd.remaining_seconds('attack'):.1f}s")
        if imap.pressed("quit", wnd):
            break


if __name__ == "__main__":
    main()
