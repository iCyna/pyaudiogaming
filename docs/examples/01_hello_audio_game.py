# -*- coding: utf-8 -*-
"""Example 01 (Beginner): Window + Speech + Non-blocking Menu."""
from pyaudiogaming.window import Window
from pyaudiogaming.menu import menu


def main():
    wnd = Window()
    wnd.init(800, 600, "PyAudioGaming — Hello Audio Game")
    m = menu()
    m.init(wnd, ttl="Main Menu", items=["Greet&G", "About&A", "Exit&E"], keyRead=True, readNP=True)
    m.open()
    while True:
        wnd.frameUpdate()
        res = m.frameUpdate()
        if res == 0:
            wnd.say("Hello! Welcome to PyAudioGaming.")
        elif res == 1:
            wnd.say("Beginner example using Window, Speech, and Menu.")
        elif res in (2, -1):
            break


if __name__ == "__main__":
    main()
