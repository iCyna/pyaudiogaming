# -*- coding: utf-8 -*-
"""Example 07: Unified Audio FX (DX8, BASS_FX, Biquad Filters, 45 Steam Audio Presets & Dynamic Strings)."""
import time
from pyaudiogaming.sound_pool import output, sound
from pyaudiogaming.sound_fx import Basic


def main():
    output(ThreeD=True)
    catalog = Basic()
    print("DX8/BFX presets:", len(catalog.fxs))
    print("Filters:", len(catalog.filters))
    print("Steam Audio presets:", len(catalog.steam_fxs))

    s = sound()
    s.stream("res/sounds/voice.ogg", ThreeD=True)
    s.play_looped()

    for preset in ("steam_hall", "steam_wall_concrete", "echo4_multitap", "rotate_stereo", "dx8_i3dl2_hall", "underwater"):
        s.remove_all_fx()
        s.setfx(preset)
        print("Applied preset:", preset)
        time.sleep(1.2)

    # Dynamic colon-string FX with live parameter tweak
    s.remove_all_fx()
    s.setfx("lowpass:900:0.707")
    s.setfx("steam_ambisonics:2")
    s.set_fx_param(cutoff=500.0)
    time.sleep(1.2)
    s.close()


if __name__ == "__main__":
    main()
