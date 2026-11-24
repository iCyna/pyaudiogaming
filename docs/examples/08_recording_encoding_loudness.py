# -*- coding: utf-8 -*-
"""Example 08: Live Microphone Recording, Native C Encoding (WAV/MP3/OGG/FLAC/OPUS), Loudness LUFS & WASAPI."""
import time
from pyaudiogaming.sound_pool import output, sound, record, WasapiManager


def main():
    output()

    # 1. Measure EBU R128 Loudness (LUFS) & True Peak
    s = sound()
    s.stream("res/sounds/music.ogg")
    s.start_loudness()
    s.play()
    time.sleep(1.5)
    print("Integrated LUFS:", s.get_loudness("integrated"), "TruePeak:", s.get_loudness("truepeak"))
    s.close()

    # 2. Record microphone & encode directly to OGG / OPUS / MP3 / FLAC / WAV
    rec = record()
    rec.start(freq=48000, chans=1, period_ms=20, gain=1.0)
    rec.start_encode("mic_capture.ogg", fmt="ogg")
    time.sleep(2.0)
    rec.stop_encode()
    rec.close()

    # 3. List Windows WASAPI devices (including loopback capture devices)
    for dev in WasapiManager.devices():
        print(dev["index"], dev["name"], "loopback=" + str(dev["is_loopback"]))


if __name__ == "__main__":
    main()
