# -*- coding: utf-8 -*-
"""Example 10: G2Access High-Performance Screen Reader & 3D BASS-Routed TTS."""
import time
from pyaudiogaming.sound_pool import output
from pyaudiogaming.speech import Speech


def main():
    output(ThreeD=True)
    sp = Speech()
    print("Available outputs:", sp.get_outputs())
    print("Active output:", sp.get_active_screen_reader())
    print("Capabilities:", sp.get_capabilities())

    # Route TTS through BASS with 3D HRTF & zone-reactive FX
    sp.set_speech_hrtf(True)
    sp.set_speech_zone_fx_provider(lambda: "steam_small_room")
    sp.set_speech_fx("zone")
    sp.say("Welcome to G2Access!")
    time.sleep(1.2)
    sp.say3d("Footsteps to your left!", 0, 0, 0, -6, 2, 0)
    time.sleep(1.5)


if __name__ == "__main__":
    main()
