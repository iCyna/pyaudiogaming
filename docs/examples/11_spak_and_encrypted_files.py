# -*- coding: utf-8 -*-
"""Example 11: Encrypted SPAK Sound Archives & AES/Fernet File Storage."""
import tempfile
from pathlib import Path
from pyaudiogaming import utils
from pyaudiogaming.file import File


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pyag_demo_"))

    # 1. Encrypted JSON save/load with File (Fernet + AES)
    store = File(password="my_secret_key", encode=True, aes=True)
    save_path = tmp / "profile.dat"
    store.save({"hero": "Knight", "gold": 500}, str(save_path), mode="wb+", type="json")
    loaded = store.load(str(save_path), mode="rb", type="json")
    print("Loaded encrypted profile:", loaded)

    # 2. Pack a folder or dict of sounds into an encrypted .spak archive
    spak_out = tmp / "sounds.spak"
    utils.make_spak({"sfx/beep.raw": b"\x00" * 64}, output_path=str(spak_out), password="demo")
    print("Created SPAK:", spak_out, spak_out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
