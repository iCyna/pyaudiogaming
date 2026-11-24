# -*- coding: utf-8 -*-
"""Example 09: Sub-Mixing (mixer), Matrix Routing, Split Streams, Realtime MIDI Synth & VST."""
import time
from pyaudiogaming.sound_pool import output, sound, mixer, musical, vst


def main():
    output()

    # 1. Sub-mixer with matrix routing
    mx = mixer()
    mx.create(frequency=44100, channels=2)
    s1 = sound()
    s1.stream("res/sounds/ambience.ogg", decode=True)
    mx.add(s1)
    s1.set_matrix([[1.0, 0.0], [0.0, 1.0]])  # stereo identity matrix
    mx.play()

    # 2. Split a single decode source into two independent channels
    src = sound()
    src.stream("res/sounds/music.ogg", decode=True)
    ch_dry = src.split()
    ch_wet = src.split()
    if ch_dry and ch_wet:
        ch_wet.setfx("hall")
        ch_dry.play()
        ch_wet.play()

    # 3. Realtime MIDI synthesizer (requires a .sf2 SoundFont)
    midi = musical()
    if midi.create_realtime(channels=16):
        # midi.load_font("res/gm.sf2")
        midi.play()
        midi.note_on(0, 60, velocity=110)  # Middle C
        time.sleep(0.4)
        midi.note_off(0, 60)
        midi.close()

    # 4. VST instrument / DSP effect control example
    # synth = vst()
    # if synth.create_instrument("plugins/MySynth.dll"):
    #     synth.set_vst_param(0, 0.75)
    #     synth.play()

    time.sleep(0.5)
    if ch_dry: ch_dry.close()
    if ch_wet: ch_wet.close()
    src.close(); s1.close(); mx.close()


if __name__ == "__main__":
    main()
