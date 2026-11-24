# -*- coding: utf-8 -*-
"""Example 05 (Advanced): 3D Binaural HRTF, slide3d, Steam Audio Wall Occlusion & Reverb."""
import time
from pyaudiogaming.sound_pool import (
    output, sound,
    add_hrtf_env_box, clear_hrtf_env_boxes, set_hrtf_auto_raycast,
    update_hrtf_listener, set_hrtf_distance_model,
)
from pyaudiogaming.sound_modules import pybass_hrtf


def main():
    output(ThreeD=True)
    set_hrtf_distance_model(min_dist=1.0, max_dist=50.0, rolloff=0.12, blend_step=0.25)

    # Register a brick wall between listener (0,0,0) and sound source (0,5,0)
    clear_hrtf_env_boxes()
    add_hrtf_env_box(pybass_hrtf.BASS_HRTF_MAT_BRICK, -5, 5, 2, 3, -2, 4)
    set_hrtf_auto_raycast(True)
    update_hrtf_listener(0, 0, 0, yaw=0.0, pitch=0.0, roll=0.0)

    s = sound()
    s.stream("res/sounds/beacon.ogg", mono=True, ThreeD=True)
    s.set_hrtf_source_radius(1.0)
    s.setfx("steam_cave", reverb_wet=0.35)
    s.play_looped()

    # Smooth C-level HRTF 3D slide from left (-6, 3, 0) to right (6, 3, 0) over 2 seconds
    s.slide3d(0, 0, 0, -6, 3, 0, 6, 3, 0, 2000, "once")
    s.slide_hrtf_attribute("occlusion", 0.7, 1000)
    time.sleep(2.2)
    s.close()


if __name__ == "__main__":
    main()
