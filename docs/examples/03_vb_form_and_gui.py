# -*- coding: utf-8 -*-
"""Example 03 (Intermediate): Unified 4-Backend Settings GUI."""
from pyaudiogaming import gui


def main():
    w = gui.Window("Settings", (520, 420), backend="auto")
    with w.page("General"):
        with w.group("Profile"):
            w.input("Username", value="Player1")
            w.checkbox("Auto Login", value=True)
        with w.group("Audio"):
            w.slider("Master Volume", 0, 100, 85)
            w.combo("Language", ["English", "Spanish", "Japanese"], value=0)
        with w.row():
            w.button("Save", lambda _: w.alert("Saved", str(w.values())))
            w.button("Close", lambda _: w.close())
    w.shortcut("ctrl+s", lambda: w.alert("Shortcut", "Quick saved!"))
    w.run()


if __name__ == "__main__":
    main()
