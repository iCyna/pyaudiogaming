# -*- coding: utf-8 -*-
"""Example 06: Tempo (speed without pitch), Tone (pitch without speed), Reverse, URL Stream, Tags & Sync."""
import time
from pyaudiogaming.sound_pool import output, sound


def main():
    output()

    # 1. Tempo & Tone on intuitive 0..100+ scale (100 = normal)
    s = sound()
    s.stream("res/sounds/music.ogg", tempo=True)
    print("Tags:", s.get_tags())
    s.on_sync("end", lambda h, c, d: print("Track finished!"))
    s.set_tempo(125)   # 125% speed, pitch unchanged
    s.set_tone(115)    # 115% pitch, speed unchanged
    s.play()
    time.sleep(2.0)
    s.fade(500, 100, type="tempo")  # smoothly return to 100% speed
    time.sleep(0.6)
    s.close()

    # 2. Tone also works on regular streams (auto BFX_PITCHSHIFT fallback)
    s2 = sound()
    s2.stream("res/sounds/voice.ogg")
    s2.set_tone(80)    # deeper voice without slowing down
    s2.play()
    time.sleep(1.5)
    s2.close()

    # 3. Reverse playback
    s3 = sound()
    s3.stream("res/sounds/sfx.ogg", reverse=True)
    s3.set_reverse_direction(True)
    s3.play()
    time.sleep(1.0)
    s3.close()

    # 4. Direct HTTP/HTTPS URL streaming (auto-detected via utils.is_url)
    radio = sound()
    radio.stream("https://example.com/stream.mp3")
    radio.on_sync("meta", lambda h, c, d: print("Now playing:", radio.get_tags()))
    radio.play()
    time.sleep(2.0)
    radio.close()


if __name__ == "__main__":
    main()
