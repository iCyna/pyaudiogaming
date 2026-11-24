# -*- coding: utf-8 -*-
"""PyAudioGaming Complete Documentation & Per-Module API Reference Generator (English).

Automatically introspects every public module in ``pyaudiogaming/`` via ``ast``
and combines extracted signatures/docstrings with detailed step-by-step usage
guides and full code examples to generate:
- Separate per-module HTML5 pages (``docs/html/modules/<mod>.html``) with dedicated parameter tables
- Separate per-module TXT references (``docs/txt/modules/<mod>.txt``)
- Separate per-module CSV & JSON parameter tables (``docs/reference/modules/<mod>.csv|.json``)
- Beginner -> Advanced tutorial chapters (``docs/html/01_*.html .. 06_*.html``)
- Complete CHM project (``docs/chm/pyaudiogaming.hhp``, nested ``toc.hhc``, ``index.hhk``)
- Runnable Python code examples (``docs/examples/*.py``)

Run: ``python pyaudiogaming/docs/build_docs.py``
"""

import ast
import csv
import html
import json
import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
PKG_DIR = DOCS_DIR.parent
HTML_DIR = DOCS_DIR / "html"
HTML_MOD_DIR = HTML_DIR / "modules"
TXT_DIR = DOCS_DIR / "txt"
TXT_MOD_DIR = TXT_DIR / "modules"
CHM_DIR = DOCS_DIR / "chm"
REF_DIR = DOCS_DIR / "reference"
REF_MOD_DIR = REF_DIR / "modules"
EX_DIR = DOCS_DIR / "examples"

TARGET_MODULES = [
	"window",
	"speech",
	"g2access",
	"sound_pool",
	"sound_fx",
	"sound_modules.control",
	"menu",
	"vb",
	"gui",
	"inputBox",
	"key",
	"timer",
	"haptics",
	"notify",
	"app_link",
	"storage",
	"worker",
	"input_map",
	"file",
	"utils",
	"buffer",
	"common",
	"system",
	"compile",
]

# ==============================================================================
# 1. CURATED MODULE SUMMARIES, DETAILED USAGE GUIDES & EXAMPLES (English)
# ==============================================================================

MODULE_GUIDES = {
	"window": {
		"title": "window — Game Window, Event Loop & Touch/Key Input",
		"summary": "Core application window managing the SDL2/pygame loop, keyboard edge/hold detection, mobile touch gestures (tap/swipe), screen-reader speech forwarding, and SPAK loading.",
		"guide": """
<h3>How to Use</h3>
<ol>
  <li>Create a <code>Window()</code> instance and call <code>wnd.init(width, height, title)</code> before creating audio/menu/form objects.</li>
  <li>Call <code>wnd.frameUpdate()</code> exactly once at the top of every main-loop iteration.</li>
  <li>Poll keyboard with <code>keyPressed(key)</code> (one-shot) or <code>keyPressing(key, t=ms)</code> (held/repeat), and mobile touch with <code>tap()</code> / <code>swipe()</code>.</li>
  <li>Call <code>wnd.say(text)</code> to speak through NVDA, JAWS, SAPI5, VoiceOver, or TalkBack.</li>
</ol>
<pre><code>from pyaudiogaming.window import Window

wnd = Window()
wnd.init(800, 600, "My Audio Game")
wnd.say("Ready! Press Space or double-tap to act, Escape to quit.")

while True:
    wnd.frameUpdate()
    if wnd.keyPressed("space") or wnd.tap(fingers=1, count=2):
        wnd.say("Action triggered!")
    if wnd.keyPressing("right", 150):
        wnd.say("Stepping right")
    if wnd.keyPressed("escape"):
        break</code></pre>
""",
	},
	"speech": {
		"title": "speech — Screen Reader, TTS & 3D Positional Speech",
		"summary": "Unified speech wrapper supporting NVDA, JAWS, SAPI5, VoiceOver, TalkBack, speech history, voice/rate/pitch/volume controls, and 3D positional TTS.",
		"guide": """
<h3>How to Use</h3>
<ul>
  <li>Use <code>say(text, i=True)</code> to interrupt current speech, or <code>i=False</code> to queue after the current utterance.</li>
  <li>Pass a list with <code>split=True</code> to speak multiple items sequentially without cutting each other off.</li>
  <li>Use <code>saync(text)</code> for transient UI hints that should not pollute <code>speech_history</code>.</li>
  <li>Use <code>say3d(text, lx, ly, lz, sx, sy, sz)</code> to speak from a 3D world coordinate.</li>
</ul>
<pre><code>from pyaudiogaming.speech import Speech

sp = Speech()
sp.say("Welcome!", i=True)
sp.say(["Health: 100", "Mana: 50"], split=True)
sp.say3d("Enemy spotted!", 0, 0, 0, 10, 4, 0)
sp.set_speech_rate(55)</code></pre>
""",
	},
	"sound_pool": {
		"title": "sound_pool — BASS Audio Engine, 3D HRTF, Tempo/Tone, URL Streaming & Recording",
		"summary": "Complete BASS audio engine: playback, 3D binaural HRTF & Steam Audio occlusion, Tempo/Tone (0..100+%), Reverse, URL streaming, LUFS loudness, native WAV/MP3/OGG/FLAC/OPUS encoding, Tags, Sync callbacks, Mixer/Split/Matrix, MIDI, VST, WASAPI, and live recording.",
		"guide": """
<h3>How to Use</h3>
<ol>
  <li>Initialize audio output once with <code>out = output(ThreeD=True)</code> (HRTF prewarms automatically without blocking startup).</li>
  <li>Stream local files, SPAK buffers, or <strong>HTTP/HTTPS URLs</strong> seamlessly via <code>s.stream(path_or_url, ThreeD=True, tempo=True, reverse=False)</code> — <code>utils.is_url()</code> automatically routes URLs through <code>BASS_StreamCreateURL</code>.</li>
  <li>Adjust speed without pitch via <code>s.set_tempo(125)</code> and pitch without speed via <code>s.set_tone(150)</code> on the intuitive <code>0..100+</code> scale (<code>100</code> = normal; <code>set_tone</code> even works on regular streams without <code>tempo=True</code>!).</li>
  <li>Move 3D sounds smoothly with <code>s.set3d(...)</code>, <code>s.slide3d(...)</code> (uses native C <code>BASS_HRTF_SlidePosition</code> for one-shot slides), <code>s.slide_hrtf_position(...)</code>, and <code>s.slide_hrtf_attribute(...)</code>.</li>
  <li>Read metadata with <code>s.get_tags()</code>, measure EBU R128 loudness via <code>s.start_loudness()</code> / <code>s.get_loudness()</code>, encode to WAV/MP3/OGG/FLAC/OPUS via <code>s.start_encode(...)</code>, attach event callbacks with <code>s.on_sync("end", cb)</code>, or use <code>WasapiManager</code> on Windows.</li>
</ol>
<pre><code>from pyaudiogaming.sound_pool import output, sound, add_hrtf_env_box, update_hrtf_listener

out = output(ThreeD=True)
s = sound()
s.stream("res/sounds/beacon.ogg", mono=True, ThreeD=True, tempo=True)
s.set_tempo(120)          # 1.2x speed, unchanged pitch
s.set_tone(115)           # +15% pitch, unchanged speed
s.setfx("steam_cave")     # Steam Audio acoustic reverb
s.slide3d(0, 0, 0, -8, 2, 0, 8, 2, 0, 1500, "once")
s.play()</code></pre>
""",
	},
	"sound_fx": {
		"title": "sound_fx — Unified FX Engine (BASS DX8, BASS_FX & 45 Steam Audio Presets)",
		"summary": "High-level DSP & Steam Audio acoustic FX catalog: 17 DX8 Reverbs, Freeverb, Echo/Echo2/Echo3/Echo4, Rotate, Chorus, Flanger, Phaser, AutoWah, Compressor, Distortion, PitchShift, 12 Biquad Filters, 45 Steam Audio presets, and dynamic colon-string parser.",
		"guide": """
<h3>How to Use</h3>
<ul>
  <li>Attach any preset by name via <code>s.setfx("preset_name", **overrides)</code>, update live with <code>s.set_fx_param(...)</code>, or remove with <code>s.remove_fx(...)</code> / <code>s.remove_all_fx()</code>.</li>
  <li><strong>Steam Audio (45 built-in presets):</strong> 16 rooms (<code>steam_small_room</code>, <code>steam_cave</code>, <code>steam_tunnel</code>, <code>steam_underwater</code>, ...), 17 materials/direct (<code>steam_wall_brick</code>, <code>steam_wall_concrete</code>, <code>steam_occlusion_heavy</code>, <code>steam_air_absorption</code>, ...), 3 multi-path (<code>steam_pathing_corridor</code>, ...), and 9 surround/ambisonics (<code>steam_virtual_surround_7_1</code>, <code>steam_ambisonics_2nd</code>, ...).</li>
  <li><strong>Dynamic Colon-String FX:</strong> Pass inline parameter strings such as <code>"reverb:0:-8:1800:0.4"</code>, <code>"lowpass:650:0.707"</code>, <code>"echo4:0.9:0.45:0.4:0.3:1"</code>, <code>"rotate:0.5"</code>, <code>"steam_reverb:1.4:1.1:0.7"</code>, <code>"steam_direct:0.8:2.5"</code>, or <code>"steam_ambisonics:2"</code>.</li>
</ul>
<pre><code>from pyaudiogaming.sound_pool import output, sound
output(ThreeD=True)
s = sound()
s.stream("res/sounds/voice.ogg", ThreeD=True)
s.setfx("steam_wall_brick", occlusion=0.75)
s.setfx("lowpass:800:0.707")
s.play()</code></pre>
""",
	},
	"g2access": {
		"title": "g2access — Compact High-Performance Screen Reader & BASS-Routed TTS Engine",
		"summary": "Zero-bloat accessibility & TTS router with shared AudioPipeline (BASS PCM, LRU cache, 3D/HRTF/FX) and dedicated OS drivers: windows.py, android.py, ios.py, macos.py, linux.py.",
		"guide": """
<h3>How to Use</h3>
<ul>
  <li>Use <code>Router()</code> (alias <code>Auto()</code>) directly or through <code>pyaudiogaming.speech.Speech()</code>.</li>
  <li>Automatically lazy-loads only the current OS drivers (<code>NVDA</code>, <code>ZDSR</code>, <code>JAWS</code>, <code>SystemAccess</code>, <code>Dolphin</code>, <code>PCTalker</code>, <code>SAPI5</code> on Windows; <code>TalkBack/Jieshuo</code> + <code>AndroidTTS</code> on Android; <code>VoiceOver</code> + <code>AVSpeech</code> / <code>say</code> on iOS/macOS; <code>SpeechDispatcher</code> + <code>eSpeak</code> on Linux).</li>
  <li>All PCM-capable TTS engines share <code>AudioPipeline</code> for instant LRU-cached playback with full BASS <code>volume</code>, <code>pan</code>, <code>mono</code>, <code>hrtf</code>, <code>fx</code>, and <code>speak3d(...)</code>.</li>
</ul>
<pre><code>from pyaudiogaming.g2access import Router

r = Router()
print("Available:", r.get_outputs(), "Active:", r.get_active_output())
r.output("Hello from G2Access!", interrupt=True)
r.speak3d("Behind you!", 0, 0, 0, 0, -5, 0)</code></pre>
""",
	},
	"sound_modules.control": {
		"title": "sound_modules.control — Core BASS Lifecycle, Codec Plugins & Zero-Copy Cache",
		"summary": "Low-level BASS initialization, on-demand codec plugin loader (FLAC, Opus, AAC, ALAC, WMA, MPC, MIDI), mmap/RAM preloading, HSAMPLE caching, and SPAK memory buffer registry.",
		"guide": """
<h3>How to Use</h3>
<p>Most apps use <code>sound_pool.output()</code>, which calls <code>control.init_sound()</code> automatically. Use <code>control</code> directly for custom memory buffers, explicit codec loading, or cache cleanup.</p>
<pre><code>from pyaudiogaming.sound_modules import control

control.init_sound(dev=-1, freq=44100)
control.load_codec_plugins()
control.load_sound_file("res/sounds/click.ogg", key="ui_click", target="both")</code></pre>
""",
	},
	"inputBox": {
		"title": "inputBox — Native OS Dialogs with Accessible SDL Fallbacks",
		"summary": "Cross-platform input prompts, message boxes, and file/folder pickers using native OS dialogs (Win32/Cocoa/GTK/Android) with automatic vb.form SDL fallback.",
		"guide": """
<h3>How to Use</h3>
<pre><code>from pyaudiogaming import inputBox

name = inputBox.kbt(None, "Player Name", "Enter your name:")
audio_path = inputBox.kbt(None, "Select Audio", "Pick a sound file", file_dialog=True)
inputBox.dialogMessage("Saved", f"Welcome, {name}!", inputBox.INFO)</code></pre>
""",
	},
	"key": {
		"title": "key — Keyboard Mapping & Chord Parser",
		"summary": "Complete key-name to pygame keycode lookup table (<code>ksum</code>) and shortcut chord parser (<code>chord('ctrl+shift+s')</code>).",
		"guide": """
<h3>How to Use</h3>
<pre><code>from pyaudiogaming import key

code = key.ksum["space"]
kc, mod_mask = key.chord("ctrl+shift+b")</code></pre>
""",
	},
	"buffer": {
		"title": "buffer — Shared Runtime Registries & Handle Buffers",
		"summary": "Central in-memory registry holding the active window frame, audio device handles, stream/sample buffers, and active sound pool references.",
		"guide": """
<h3>How to Use</h3>
<p>Managed automatically by <code>Window</code>, <code>sound_pool</code>, and <code>speech</code>. Inspect <code>buffer.frame</code> or <code>buffer.hAudiobuffers</code> when integrating custom extensions.</p>
""",
	},
	"common": {
		"title": "common — System & Process Utility Helpers",
		"summary": "Lightweight filesystem, process execution, and environment utilities shared across PyAudioGaming modules.",
		"guide": """
<h3>How to Use</h3>
<p>Helper utilities used internally by build and runtime tools.</p>
""",
	},
	"menu": {
		"title": "menu — Non-Blocking Accessible Menus",
		"summary": "Accessible game menu supporting keyboard arrows, '&K' shortcut hotkeys, wrap-around navigation, custom cursor/enter/cancel sounds, and mobile TalkBack touch gestures.",
		"guide": """
<h3>How to Use</h3>
<ol>
  <li>Create <code>m = menu()</code> and call <code>m.init(wnd, ttl='Title', items=['Start&amp;S', 'Options&amp;O', 'Exit&amp;E'])</code>.</li>
  <li>Call <code>m.open()</code> once before entering your loop.</li>
  <li>Inside your loop, call <code>res = m.frameUpdate()</code>: it returns <code>None</code> while browsing, <code>-1</code> on Escape/Cancel, or the <code>0</code>-based item index when activated.</li>
</ol>
<pre><code>from pyaudiogaming.menu import menu

m = menu()
m.init(wnd, ttl="Main Menu", items=["Play&amp;P", "Settings&amp;S", "Quit&amp;Q"], keyRead=True, readNP=True)
m.open()

while True:
    wnd.frameUpdate()
    res = m.frameUpdate()
    if res == 0: start_game()
    elif res == 1: open_settings()
    elif res in (2, -1): break</code></pre>
""",
	},
	"vb": {
		"title": "vb — Virtual Box (Accessible Input, Rich Forms & Modal Boxes)",
		"summary": "NVDA & TalkBack accessible UI engine featuring advanced text input (with Ctrl+Shift+Alt+Backspace neutral keyboard mode switcher), 23-control forms (group, tab, link, switch, table, tree, slider), and ready-to-use modal boxes.",
		"guide": """
<h3>How to Use</h3>
<ul>
  <li><strong>Text Input:</strong> <code>vb.input(title, text, password=False)</code> — supports Undo/Redo (<code>Ctrl+Z/Y</code>), copy/paste, autocomplete suggestions, <code>Ctrl+Shift+P</code> (toggle password visibility), <code>Ctrl+Shift+F</code> (announce style), and <strong><code>Ctrl+Shift+Alt+Backspace</code></strong> to cycle neutral virtual keyboard modes (<code>standard</code>, <code>numeric</code>, <code>symbols</code>, <code>emoji</code>, <code>custom_keyboards</code>).</li>
  <li><strong>Forms:</strong> Build structured forms with <code>vb.form()</code>, <code>begin_group()</code>/<code>end_group()</code>, <code>add(..., required=True, validator=fn)</code>, <code>validate()</code>, and <code>open()</code>.</li>
  <li><strong>Modal Boxes:</strong> <code>info_box()</code>, <code>warning_box()</code>, <code>success_box()</code>, <code>error_box(details=...)</code> (with Copy Details button), <code>choice_box()</code>, <code>progress_box()</code>, <code>confirm()</code>.</li>
</ul>
<pre><code>from pyaudiogaming import vb

f = vb.form(window=wnd, config={"label": "User Registration"})
f.begin_group("Account")
f.add("user", "input", value="", required=True, label="Username")
f.add("notify", "switch", value=True, label="Notifications")
f.add("docs", "link", url="https://example.com", label="Terms of Service")
f.end_group()
f.add("ok", "button", label="Register")
if f.open() == "ok":
    ok, errs = f.validate()
    if ok:
        vb.success_box("Done", f"Welcome, {f.get('user')}!")</code></pre>
""",
	},
	"gui": {
		"title": "gui — Unified 4-Backend Cross-Platform GUI (wx / Qt / Tk / Audio)",
		"summary": "Write GUI code once and run natively on wxPython (Windows), PySide6/PyQt6 (Linux/macOS), Tkinter (stdlib fallback), or AudioWindow/vb.form (Android/iOS/Web).",
		"guide": """
<h3>How to Use</h3>
<ul>
  <li>Create <code>w = gui.Window("Title", (520, 420), backend="auto")</code> (or force <code>"wx"</code>, <code>"qt"</code>, <code>"tk"</code>, <code>"audio"</code>).</li>
  <li>Organize layouts effortlessly with <code>with w.page("Tab"):</code>, <code>with w.group("Section"):</code>, and <code>with w.row():</code>.</li>
  <li>Read/write any control uniformly via <code>w.get(label)</code>, <code>w.set(label, val)</code>, and <code>w.values()</code>.</li>
  <li>Or declare an entire UI in one list via <code>w.build([...])</code>.</li>
</ul>
<pre><code>from pyaudiogaming import gui

w = gui.Window("Preferences", (520, 420))
with w.page("General"):
    with w.group("Profile"):
        w.input("Username", value="player1")
        w.spin("Level", 1, 99, 10)
    with w.row():
        w.button("Save", lambda _: w.alert("Saved", str(w.values())))
        w.button("Close", lambda _: w.close())
w.shortcut("ctrl+s", lambda: w.alert("Shortcut", "Saved!"))
w.run()</code></pre>
""",
	},
	"timer": {
		"title": "timer — Single-Threaded High-Precision Timers, Cooldowns & Scheduler",
		"summary": "Zero-thread, nanosecond-precision monotonic timing suite: Timer (pause/scale/countdown/drift-free), CooldownManager, TimerScheduler (min-heap), FrameClock (FPS/dt/fixed_steps), Stopwatch, and RateLimiter.",
		"guide": """
<h3>How to Use</h3>
<ul>
  <li><strong>Basic Timer:</strong> <code>t = Timer()</code>, check <code>t.elapsed</code> (int ms), call <code>t.restart()</code>. Works before <code>pygame.init()</code> and on headless servers.</li>
  <li><strong>Cooldowns:</strong> Use <code>CooldownManager()</code> and <code>if cd.use("skill", 2000): ...</code>.</li>
  <li><strong>Scheduled Callbacks:</strong> Use <code>TimerScheduler()</code> with <code>after(ms, fn)</code> / <code>every(ms, fn)</code> and call <code>sched.update()</code> each frame (100% single-threaded).</li>
</ul>
<pre><code>from pyaudiogaming.timer import Timer, CooldownManager, TimerScheduler, FrameClock

cd = CooldownManager()
sched = TimerScheduler()
clock = FrameClock(target_fps=60)

if cd.use("fireball", 3000):
    sched.after(3000, lambda: print("Fireball ready!"))
# Each frame:
dt = clock.tick()
sched.update()</code></pre>
""",
	},
	"haptics": {
		"title": "haptics — Cross-Platform Vibration & Gamepad Rumble",
		"summary": "Unified vibration & rumble controller for Android (Vibrator/VibrationEffect), iOS (UIImpactFeedbackGenerator), Windows XInput gamepads, and SDL2/pygame joysticks with 13 built-in presets and non-blocking patterns.",
		"guide": """
<h3>How to Use</h3>
<ol>
  <li>Trigger instant feedback with <code>haptics.preset("click")</code>, <code>haptics.preset("hit_heavy")</code>, or <code>haptics.vibrate(duration_ms=60, strength=0.8)</code>.</li>
  <li>Play multi-step rhythms with <code>haptics.pattern([(40, 0.8), (60, 0.0), (100, 1.0)])</code>.</li>
  <li>Call <code>haptics.update()</code> once per frame in your game loop.</li>
</ol>
<pre><code>from pyaudiogaming import haptics

haptics.set_intensity(0.85)
haptics.preset("explosion")
# Inside game loop:
haptics.update()</code></pre>
""",
	},
	"notify": {
		"title": "notify — System Notifications & Lock-Screen Full-Screen Call/Alarm Wake",
		"summary": "Send native OS notifications (Windows Toast, Android NotificationManager, macOS, Linux) and wake locked/sleeping screens with Full-Screen Intent (Android) or Win32 display wake & foreground bring-to-front (Windows).",
		"guide": """
<h3>How to Use</h3>
<pre><code>from pyaudiogaming import notify

# 1. Standard OS notification
notify.send("New Message", "Alice invited you to a party.")

# 2. Wake locked/sleeping screen &amp; pop app to front (Incoming Call / Alarm)
notify.wake_and_show("Incoming Call", "Alice is calling...", category="call")</code></pre>
""",
	},
	"app_link": {
		"title": "app_link — File Associations, Android URI Resolver & Single-Instance IPC",
		"summary": "Register file extensions (.mp3, .ogg, .wav) without Admin on Windows (HKCU) or Linux (.desktop), read launched files / Android content:// URIs, and forward newly opened files to an already-running app instance.",
		"guide": """
<h3>How to Use</h3>
<pre><code>import sys
from pyaudiogaming import app_link

# Register .mp3 / .ogg (no Admin needed on Windows!)
app_link.register_file_association([".mp3", ".ogg"], app_name="My Music Player")

# Enforce Single Instance so pressing Enter on a 2nd song plays in the existing window
inst = app_link.SingleInstance("my_music_player")
if not inst.is_primary:
    inst.send_args(app_link.get_launch_files())
    sys.exit(0)

first_song = app_link.get_launch_file()
# Inside your main loop:
for new_files in inst.poll():
    if new_files:
        play_song(app_link.resolve_uri_to_file(new_files[0]))</code></pre>
""",
	},
	"storage": {
		"title": "storage — Cross-Platform Persistent Storage & ConfigStore",
		"summary": "Guaranteed-writable persistent storage solving mobile APK asset overwrites: uses filesDir ($HOME) on Android/iOS, AppData/XDG/portable on Desktop, with atomic writes (.tmp + fsync + os.replace) and automatic .bak recovery.",
		"guide": """
<h3>How to Use</h3>
<ul>
  <li>Use <code>ConfigStore</code> for settings (dict-like access, schema defaults, JSON/Pickle/AES encryption, and version migration).</li>
  <li>Use <code>Storage</code> directly for arbitrary save files, account files, logs, or encrypted payloads.</li>
</ul>
<pre><code>from pyaudiogaming.storage import ConfigStore, Storage

cfg = ConfigStore("my_game", filename="data/options.json", defaults={"vol": 90.0}, portable=True)
cfg.load()
cfg["vol"] = 75.0
cfg.save()

st = Storage("my_game", portable=True)
st.save_encrypted("data/account.dat", {"user": "alice"}, password="secret")</code></pre>
""",
	},
	"worker": {
		"title": "worker — Cross-Platform Background TaskPool & SharedState",
		"summary": "Run heavy CPU/IO tasks without freezing your game loop. Automatically selects process on Desktop (with freeze_support and auto-thread fallback for lambdas), thread on Android/iOS, and inline on Web.",
		"guide": """
<h3>How to Use</h3>
<ol>
  <li>Create <code>pool = TaskPool(mode="auto")</code>.</li>
  <li>Submit work via <code>pool.submit(fn, *args, on_done=callback, on_error=err_cb)</code>.</li>
  <li>Call <code>pool.poll()</code> inside your main loop so <code>on_done</code> runs safely on the main game thread.</li>
</ol>
<pre><code>from pyaudiogaming.worker import TaskPool, SharedState

def compute(n):
    return sum(i * i for i in range(n))

pool = TaskPool(mode="auto")
pool.submit(compute, 100000, on_done=lambda res: print("Done:", res))
# Each frame:
pool.poll()</code></pre>
""",
	},
	"input_map": {
		"title": "input_map — Unified Keyboard, Touch, Mouse & Gamepad Action Mapping",
		"summary": "Map named actions to keyboard keys/chords, mobile touch taps/swipes, mouse buttons, and gamepad buttons/sticks, with interactive rebinding, TTS descriptions, and JSON persistence.",
		"guide": """
<h3>How to Use</h3>
<pre><code>from pyaudiogaming.input_map import InputMap

imap = InputMap({
    "jump":       ["space", "tap:1:2:left-play", "pad:a"],
    "save":       ["ctrl+s", "pad:start"],
    "move_left":  ["left", "swipe:left", "pad:lx-"],
    "move_right": ["right", "swipe:right", "pad:lx+"],
})

if imap.pressed("jump", wnd):
    player.jump()
dx = imap.axis("move_left", "move_right", wnd)
imap.save("keymap.json")</code></pre>
""",
	},
	"file": {
		"title": "file — Encrypted File I/O (Fernet + AES-CBC)",
		"summary": "File helper supporting JSON, Pickle, and plain-text serialization with optional two-layer Fernet + AES-CBC encryption.",
		"guide": """
<h3>How to Use</h3>
<pre><code>from pyaudiogaming.file import File

f = File(password="my_key", encode=True, aes=True)
f.save({"user": "alice", "score": 500}, "save.dat", mode="wb+", type="json")
data = f.load("save.dat", mode="rb+", type="json")</code></pre>
""",
	},
	"utils": {
		"title": "utils — Math, Spatial, Formatting, Search, Clipboard & SPAK Archive Toolkit",
		"summary": "Zero-dependency game utilities: clamp/lerp/remap/clock_direction/db_to_linear, weighted random, fuzzy search, cross-platform clipboard (copy_text/paste_text), open_url, SHA-256 hashing, and SPAK binary audio archiving.",
		"guide": """
<h3>How to Use</h3>
<pre><code>from pyaudiogaming import utils

hour = utils.clock_direction(dx=5, dy=1)             # 3 (3 o'clock)
hits = utils.fuzzy_match("aud", ["Audio", "Video"])
utils.copy_text("Hello clipboard!")
utils.make_spak("res/sounds", "res/sounds.zb", password="pw")</code></pre>
""",
	},
	"system": {
		"title": "system — Platform, Architecture & Native Library Loader",
		"summary": "Detects OS (Windows/Linux/macOS/Android/iOS), CPU architecture (x64/x86/arm64-v8a/aarch64/armhf), frozen bundle paths, and loads platform-specific native libraries (.dll/.so/.dylib).",
		"guide": """
<h3>How to Use</h3>
<pre><code>from pyaudiogaming import system

print(system.get_platform())   # {'os': 'windows', ...}
print(system.get_arch())       # {'bit': 64, 'machine': 'amd64', ...}
lib_path = system.get_path("bass")</code></pre>
""",
	},
	"compile": {
		"title": "compile — Unified Cross-Platform Builder (Windows, Linux, macOS, Android, iOS, Web)",
		"summary": "Single-config build tool driving PyInstaller, Nuitka, Cython/GCC/MSVC, cx_Freeze, and BeeWare (Briefcase) for Desktop, Android APK, iOS Xcode/IPA, and Web.",
		"guide": """
<h3>How to Use</h3>
<pre><code># Generate template build.txt
python -m pyaudiogaming.compile create build.txt

# Launch interactive wizard
python -m pyaudiogaming.compile make

# Build from config file
python -m pyaudiogaming.compile build.txt</code></pre>
""",
	},
}


# ==============================================================================
# 2. AST INTROSPECTION ENGINE (Extracts EVERY Public Class, Method & Function)
# ==============================================================================

def _unparse_safe(node):
	if node is None:
		return ""
	try:
		return ast.unparse(node)
	except Exception:
		return "..."


def _extract_params(args_node: ast.arguments, is_method: bool = False) -> list:
	"""Return list of dicts: {name, type, default} for a function's arguments."""
	params = []
	pos_args = list(args_node.posonlyargs) + list(args_node.args)
	if is_method and pos_args and pos_args[0].arg in ("self", "cls"):
		pos_args = pos_args[1:]

	num_defaults = len(args_node.defaults)
	default_offset = len(pos_args) - num_defaults
	for idx, a in enumerate(pos_args):
		d_idx = idx - default_offset
		d_val = _unparse_safe(args_node.defaults[d_idx]) if d_idx >= 0 else ""
		params.append({
			"name": a.arg,
			"type": _unparse_safe(a.annotation) or "any",
			"default": d_val or "required",
		})

	if args_node.vararg:
		params.append({
			"name": "*" + args_node.vararg.arg,
			"type": _unparse_safe(args_node.vararg.annotation) or "tuple",
			"default": "optional",
		})

	for a, d in zip(args_node.kwonlyargs, args_node.kw_defaults):
		params.append({
			"name": a.arg,
			"type": _unparse_safe(a.annotation) or "any",
			"default": _unparse_safe(d) if d is not None else "required",
		})

	if args_node.kwarg:
		params.append({
			"name": "**" + args_node.kwarg.arg,
			"type": _unparse_safe(args_node.kwarg.annotation) or "dict",
			"default": "optional",
		})
	return params


def _format_sig(params: list) -> str:
	parts = []
	for p in params:
		s = p["name"]
		if p["type"] not in ("any", "tuple", "dict"):
			s += f": {p['type']}"
		if p["default"] not in ("required", "optional"):
			s += f"={p['default']}"
		parts.append(s)
	return ", ".join(parts)


def _short_doc(node) -> str:
	doc = ast.get_docstring(node) or ""
	if not doc:
		return ""
	first_para = doc.strip().split("\n\n")[0]
	return " ".join(line.strip() for line in first_para.splitlines())


def introspect_module(mod_name: str) -> dict:
	"""Parse ``pyaudiogaming/<mod_name>.py`` (or package directory / dotted path) with ``ast``."""
	parts = mod_name.split(".")
	cand_file = PKG_DIR.joinpath(*parts[:-1], f"{parts[-1]}.py")
	cand_dir = PKG_DIR.joinpath(*parts)
	py_files = []
	if cand_file.is_file():
		py_files = [cand_file]
	elif cand_dir.is_dir():
		py_files = sorted(p for p in cand_dir.glob("*.py") if p.name != "__init__.py")
	result = {"module": mod_name, "classes": [], "functions": []}
	if not py_files:
		return result

	seen_cls, seen_fn = set(), set()
	for py_path in py_files:
		tree = ast.parse(py_path.read_text(encoding="utf-8", errors="replace"), filename=str(py_path))
		for node in tree.body:
			if isinstance(node, ast.ClassDef):
				if node.name.startswith("_") or node.name in seen_cls:
					continue
				seen_cls.add(node.name)
				cls_info = {
					"name": node.name,
					"doc": _short_doc(node),
					"methods": [],
				}
				for item in node.body:
					if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
						if item.name.startswith("_") and item.name != "__init__":
							continue
						is_prop = any(
							(isinstance(d, ast.Name) and d.id == "property")
							or (isinstance(d, ast.Attribute) and d.attr == "setter")
							for d in item.decorator_list
						)
						is_setter = any(isinstance(d, ast.Attribute) and d.attr == "setter" for d in item.decorator_list)
						if is_setter:
							continue
						is_static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in item.decorator_list)
						params = _extract_params(item.args, is_method=not is_static)
						cls_info["methods"].append({
							"name": item.name,
							"kind": "property" if is_prop else ("constructor" if item.name == "__init__" else "method"),
							"signature": _format_sig(params),
							"params": params,
							"returns": _unparse_safe(item.returns) or "any",
							"doc": _short_doc(item),
						})
				result["classes"].append(cls_info)
			elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
				if node.name.startswith("_") or node.name in seen_fn:
					continue
				seen_fn.add(node.name)
				params = _extract_params(node.args, is_method=False)
				result["functions"].append({
					"name": node.name,
					"kind": "function",
					"signature": _format_sig(params),
					"params": params,
					"returns": _unparse_safe(node.returns) or "any",
					"doc": _short_doc(node),
				})
	return result


# ==============================================================================
# 3. TUTORIAL CHAPTERS (Beginner -> Advanced) & RUNNABLE EXAMPLES
# ==============================================================================

TUTORIAL_PAGES = [
	{
		"filename": "index.html",
		"title": "PyAudioGaming — Official Documentation (Beginner to Advanced)",
		"nav": "Home",
		"body": """
<h2>1. Overview</h2>
<p><strong>PyAudioGaming</strong> is a complete Python framework for building <strong>audio games</strong> and <strong>accessible cross-platform applications</strong> targeting <strong>Windows, Linux, macOS, Android, iOS, and Web</strong>.</p>
<div class="callout">
  <strong>Documentation Structure:</strong>
  <ul>
    <li><strong>Step-by-Step Tutorials (01 &rarr; 06):</strong> Learn everything from your first window to 3D HRTF audio, forms, multi-backend GUI, storage, background workers, and shipping builds.</li>
    <li><strong>Dedicated Per-Module Guides &amp; Parameter Tables:</strong> Every module has its own dedicated HTML page, TXT file, CSV spreadsheet, and JSON schema — never crammed into a single unreadable table.</li>
    <li><strong>Runnable Code Examples:</strong> Complete working Python scripts in <code>docs/examples/</code>.</li>
  </ul>
</div>
<h2>2. Learning Path (Beginner &rarr; Advanced)</h2>
<table>
  <thead><tr><th>Level</th><th>Tutorial</th><th>Topics Covered</th></tr></thead>
  <tbody>
    <tr><td>Level 1</td><td><a href="01_getting_started.html">01. Getting Started</a></td><td>Setup, Window, game loop, Speech, first sound.</td></tr>
    <tr><td>Level 2</td><td><a href="02_window_input_menu.html">02. Window, InputMap &amp; Menu</a></td><td>Keyboard, mobile touch, gamepad actions, non-blocking menus.</td></tr>
    <tr><td>Level 3</td><td><a href="03_audio_3d_fx.html">03. 3D Audio, HRTF &amp; SPAK</a></td><td>BASS engine, binaural HRTF, Steam Audio occlusion, recording, SPAK.</td></tr>
    <tr><td>Level 4</td><td><a href="04_speech_vb_gui.html">04. Speech, Virtual Box &amp; GUI</a></td><td>3D TTS, <code>vb.input</code> keyboard switcher, <code>vb.form</code>, boxes, 4-backend <code>gui.Window</code>.</td></tr>
    <tr><td>Level 5</td><td><a href="05_timer_worker_storage_haptics.html">05. Timer, Worker, Storage &amp; Haptics</a></td><td>High-precision timers, cooldowns, mobile-safe saves, background tasks, vibration.</td></tr>
    <tr><td>Level 6</td><td><a href="06_building_cross_platform.html">06. Cross-Platform Building</a></td><td>Building for Windows, Android APK, Linux, macOS, iOS, and Web.</td></tr>
    <tr><td>Reference</td><td><a href="api_reference.html">Per-Module Reference Hub</a></td><td>Browse dedicated parameter tables &amp; full API docs for all 16 modules.</td></tr>
  </tbody>
</table>
""",
	},
	{
		"filename": "01_getting_started.html",
		"title": "01. Getting Started (Beginner)",
		"nav": "01. Getting Started",
		"body": """
<h2>1. Installation</h2>
<pre><code>pip install pygame pycryptodome cryptography polib
pip install wxPython   # Optional: Windows native GUI (best NVDA/JAWS support)
pip install PySide6    # Optional: Linux/macOS native GUI
pip install pyinstaller nuitka briefcase   # Optional: packaging tools</code></pre>
<h2>2. Complete First Program</h2>
<pre><code>from pyaudiogaming.window import Window
from pyaudiogaming.sound_pool import output, sound

wnd = Window()
wnd.init(800, 600, "My First Audio Game")
audio = output()

bgm = sound()
if bgm.stream("res/sounds/intro.ogg"):
    bgm.volume = 50
    bgm.play_looped()

wnd.say("Welcome! Press Space to say hello, Escape to exit.")
while True:
    wnd.frameUpdate()
    if wnd.keyPressed("space"):
        wnd.say("Hello from PyAudioGaming!")
    if wnd.keyPressed("escape"):
        bgm.fadeout(400)
        wnd.wait(400)
        break</code></pre>
<p>Next: <a href="02_window_input_menu.html">02. Window, InputMap &amp; Menu</a> | Full API: <a href="modules/window.html">window module</a></p>
""",
	},
	{
		"filename": "02_window_input_menu.html",
		"title": "02. Window, InputMap & Non-Blocking Menus",
		"nav": "02. Input & Menu",
		"body": """
<h2>1. Unified Controls Across PC, Mobile &amp; Gamepad</h2>
<pre><code>from pyaudiogaming.input_map import InputMap

imap = InputMap({
    "jump":       ["space", "tap:1:2:left-play", "pad:a"],
    "attack":     ["ctrl+space", "tap:2:1", "pad:x"],
    "move_left":  ["left", "a", "swipe:left", "pad:lx-"],
    "move_right": ["right", "d", "swipe:right", "pad:lx+"],
})
if imap.pressed("jump", wnd): player.jump()
dx = imap.axis("move_left", "move_right", wnd)
imap.save("keymap.json")</code></pre>
<h2>2. Non-Blocking Accessible Menu</h2>
<pre><code>from pyaudiogaming.menu import menu

m = menu()
m.init(wnd, ttl="Main Menu", items=["Start&amp;S", "Settings&amp;O", "Exit&amp;E"], keyRead=True, readNP=True)
m.open()
while True:
    wnd.frameUpdate()
    choice = m.frameUpdate()
    if choice == 0: play_game()
    elif choice == 1: open_settings()
    elif choice in (2, -1): break</code></pre>
<p>Module References: <a href="modules/input_map.html">input_map</a> | <a href="modules/menu.html">menu</a> | <a href="modules/window.html">window</a></p>
""",
	},
	{
		"filename": "03_audio_3d_fx.html",
		"title": "03. 3D Audio, HRTF, Steam Audio & SPAK",
		"nav": "03. 3D Audio",
		"body": """
<h2>1. 3D Binaural HRTF &amp; Steam Audio Wall Occlusion</h2>
<pre><code>from pyaudiogaming.sound_pool import output, sound, update_hrtf_listener, hrtf_add_box_preset, hrtf_set_auto_raycast

out = output(device=-1, frequency=44100)
hrtf_set_auto_raycast(True)
hrtf_add_box_preset(1, min_x=4, max_x=5, min_y=-6, max_y=6, min_z=0, max_z=4)

s = sound()
s.stream("res/sounds/beacon.ogg", mono=True)
s.attach_hrtf_dsp()
s.play_looped()

update_hrtf_listener(0, 0, 1.7, 0, 1, 0, 0, 0, 1)</code></pre>
<h2>2. Encrypted SPAK Sound Archives</h2>
<pre><code>from pyaudiogaming.utils import make_spak, load_spak

make_spak("res/sounds", output_path="res/sounds.zb", password="pw", encrypt_bytes=256)
load_spak("res/sounds.zb", password="pw", mode="lazy", target="both")</code></pre>
<p>Module References: <a href="modules/sound_pool.html">sound_pool</a> | <a href="modules/sound_fx.html">sound_fx</a> | <a href="modules/utils.html">utils</a></p>
""",
	},
	{
		"filename": "04_speech_vb_gui.html",
		"title": "04. Speech, Virtual Box (vb) & 4-Backend GUI (gui)",
		"nav": "04. Speech, VB & GUI",
		"body": """
<h2>1. Virtual Box Input &amp; Neutral Keyboard Mode Switcher</h2>
<p>Press <strong><code>Ctrl + Shift + Alt + Backspace</code></strong> inside <code>vb.input()</code> to cycle neutral virtual keyboard modes (<code>standard</code>, <code>numeric</code>, <code>symbols</code>, <code>emoji</code>, or your own <code>custom_keyboards</code>).</p>
<pre><code>from pyaudiogaming import vb

msg = vb.input("Message", placeholder="Press Ctrl+Shift+Alt+Backspace for symbols...", window=wnd)
vb.info_box("Sent", f"You typed: {msg}")</code></pre>
<h2>2. 4-Backend Cross-Platform GUI (wx / Qt / Tk / Audio)</h2>
<pre><code>from pyaudiogaming import gui

w = gui.Window("Settings", (520, 420), backend="auto")
with w.page("General"):
    with w.group("Profile"):
        w.input("Username", value="player1")
        w.spin("Level", 1, 99, 10)
    with w.row():
        w.button("Save", lambda _: w.alert("Saved", str(w.values())))
        w.button("Close", lambda _: w.close())
w.run()</code></pre>
<p>Module References: <a href="modules/speech.html">speech</a> | <a href="modules/vb.html">vb</a> | <a href="modules/gui.html">gui</a></p>
""",
	},
	{
		"filename": "05_timer_worker_storage_haptics.html",
		"title": "05. Timer, Worker, Storage, Haptics & Utils",
		"nav": "05. Advanced Systems",
		"body": """
<h2>1. Timers, Cooldowns &amp; Single-Threaded Scheduler</h2>
<pre><code>from pyaudiogaming.timer import Timer, CooldownManager, TimerScheduler, FrameClock

cd = CooldownManager()
sched = TimerScheduler()
if cd.use("dash", 2000):
    sched.after(2000, lambda: wnd.say("Dash ready!"))
sched.update()</code></pre>
<h2>2. Mobile-Safe Storage, Background Workers &amp; Haptics</h2>
<pre><code>from pyaudiogaming.storage import ConfigStore
from pyaudiogaming.worker import TaskPool
from pyaudiogaming import haptics

cfg = ConfigStore("my_game", defaults={"vol": 90.0}, portable=True)
cfg.load(); cfg["vol"] = 80.0; cfg.save()

pool = TaskPool(mode="auto")
pool.submit(sum, range(500000), on_done=lambda total: print("Total:", total))
pool.poll()

haptics.preset("hit_heavy")
haptics.update()</code></pre>
<p>Module References: <a href="modules/timer.html">timer</a> | <a href="modules/storage.html">storage</a> | <a href="modules/worker.html">worker</a> | <a href="modules/haptics.html">haptics</a> | <a href="modules/utils.html">utils</a></p>
""",
	},
	{
		"filename": "06_building_cross_platform.html",
		"title": "06. Cross-Platform Building & Shipping (compile.py)",
		"nav": "06. Building",
		"body": """
<h2>1. Sample <code>build.txt</code></h2>
<pre><code>project = main
project_full_name = my_audio_game
rename_file = game
args_compile = [--noconsole]
data = [res]
mode = pyinstaller      # pyinstaller | nuitka | cython | gcc | cx_freeze | beeware
platforms = windows     # windows | linux | macos | android | ios | web
arch = null</code></pre>
<h2>2. Build Commands</h2>
<pre><code>python -m pyaudiogaming.compile create build.txt
python -m pyaudiogaming.compile make
python -m pyaudiogaming.compile build.txt</code></pre>
<p>Module Reference: <a href="modules/compile.html">compile</a> | <a href="modules/system.html">system</a></p>
""",
	},
]

EXAMPLES = {
	"01_hello_audio_game.py": '''# -*- coding: utf-8 -*-
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
''',
	"02_input_map_and_haptics.py": '''# -*- coding: utf-8 -*-
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
''',
	"03_vb_form_and_gui.py": '''# -*- coding: utf-8 -*-
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
''',
	"04_storage_and_worker.py": '''# -*- coding: utf-8 -*-
"""Example 04 (Advanced): Mobile-Safe ConfigStore + Cross-Platform TaskPool."""
from pyaudiogaming.storage import ConfigStore
from pyaudiogaming.worker import TaskPool


def heavy_sum(n):
    return sum(i * i for i in range(n))


def main():
    cfg = ConfigStore("demo_game", defaults={"volume": 80, "level": 1}, portable=True)
    cfg.load()
    cfg["level"] += 1
    cfg.save()
    print("Config:", cfg.to_dict())
    with TaskPool(mode="auto") as pool:
        job = pool.submit(heavy_sum, 200_000, on_done=lambda r: print("Worker result:", r))
        pool.wait(job)


if __name__ == "__main__":
    main()
''',
	"05_advanced_3d_audio_hrtf.py": '''# -*- coding: utf-8 -*-
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
''',
	"06_tempo_tone_reverse_url.py": '''# -*- coding: utf-8 -*-
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
''',
	"07_audio_fx_and_steam_presets.py": '''# -*- coding: utf-8 -*-
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
''',
	"08_recording_encoding_loudness.py": '''# -*- coding: utf-8 -*-
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
''',
	"09_mixer_split_midi_vst.py": '''# -*- coding: utf-8 -*-
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
''',
	"10_g2access_speech_3d.py": '''# -*- coding: utf-8 -*-
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
''',
	"11_spak_and_encrypted_files.py": '''# -*- coding: utf-8 -*-
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
    utils.make_spak({"sfx/beep.raw": b"\\x00" * 64}, output_path=str(spak_out), password="demo")
    print("Created SPAK:", spak_out, spak_out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
''',
	"12_notify_app_link_timer.py": '''# -*- coding: utf-8 -*-
"""Example 12: System Notifications, File Associations (app_link), InputBox & Precision Timers."""
import time
from pyaudiogaming import notify, app_link
from pyaudiogaming.timer import Timer, CooldownManager, TimerScheduler


def main():
    # 1. High-precision Timer, CooldownManager, and TimerScheduler (works headless)
    t = Timer()
    cd = CooldownManager()
    sched = TimerScheduler()
    sched.after(150, lambda: print(f"Scheduled event fired at {t.elapsed} ms!"))

    if cd.use("ping", 1000):
        print("Cooldown 'ping' started, remaining:", round(cd.remaining_seconds("ping"), 2), "s")

    for _ in range(25):
        sched.update()
        time.sleep(0.01)

    # 2. Launch URI / file-open argument reader
    print("Launch URI/path:", app_link.get_launch_uri())

    # 3. System notification (Windows Toast / Android Notification / macOS / Linux)
    notify.send("PyAudioGaming", "Background task completed!")


if __name__ == "__main__":
    main()
''',
}

CSS = """/* PyAudioGaming Accessible Documentation Stylesheet */
:root {
  --bg: #0f1219; --panel: #171c26; --text: #e8ecf5; --muted: #a5b0c7;
  --accent: #6cb4ff; --border: #2a3345; --code-bg: #111622;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f8fafc; --panel: #ffffff; --text: #111827; --muted: #4b5563;
    --accent: #1d4ed8; --border: #d1d5db; --code-bg: #f1f5f9;
  }
}
* { box-sizing: border-box; }
body { margin: 0; font-family: "Segoe UI", Roboto, Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.65; }
.skip-link { position: absolute; left: -9999px; }
.skip-link:focus { left: 12px; top: 12px; background: var(--accent); color: #fff; padding: 8px 14px; border-radius: 6px; z-index: 100; }
header { background: var(--panel); border-bottom: 1px solid var(--border); padding: 16px 24px; }
header h1 { margin: 0 0 8px 0; font-size: 1.45rem; color: var(--accent); }
nav { display: flex; flex-wrap: wrap; gap: 8px; }
nav a { color: var(--text); text-decoration: none; padding: 5px 10px; border-radius: 6px; border: 1px solid var(--border); font-size: 0.9rem; }
nav a:hover, nav a.active { background: var(--accent); color: #0b1020; font-weight: 600; }
main { max-width: 1160px; margin: 24px auto; padding: 0 20px 60px; }
h2 { color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-top: 28px; }
h3 { margin-top: 22px; color: var(--text); }
pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px; padding: 14px; overflow-x: auto; }
code { font-family: Consolas, "Courier New", monospace; font-size: 0.9rem; }
.callout { background: var(--panel); border-left: 4px solid var(--accent); padding: 14px 18px; border-radius: 6px; margin: 16px 0; }
.badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.78rem; background: var(--code-bg); border: 1px solid var(--border); color: var(--accent); margin-right: 6px; }
table { width: 100%; border-collapse: collapse; margin: 14px 0 22px; background: var(--panel); }
th, td { border: 1px solid var(--border); padding: 9px 11px; text-align: left; vertical-align: top; }
th { background: var(--code-bg); color: var(--accent); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; margin: 18px 0; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
.card h3 { margin: 0 0 6px; font-size: 1.05rem; }
.card a { color: var(--accent); text-decoration: none; font-weight: 600; }
.card p { margin: 6px 0 0; font-size: 0.9rem; color: var(--muted); }
input[type="search"] { width: 100%; padding: 10px 14px; margin: 12px 0; border-radius: 6px; border: 1px solid var(--border); background: var(--panel); color: var(--text); font-size: 1rem; }
footer { text-align: center; padding: 20px; color: var(--muted); border-top: 1px solid var(--border); font-size: 0.88rem; }
"""


def _render_html(filename, title, body_html, depth=0):
	prefix = "../" * depth
	nav_items = [(p["filename"], p["nav"]) for p in TUTORIAL_PAGES] + [("api_reference.html", "Module Reference")]
	nav_html = "\n".join(
		f'    <a href="{prefix}{fn}" class="{"active" if (depth == 0 and fn == filename) else ""}">{html.escape(lbl)}</a>'
		for fn, lbl in nav_items
	)
	return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{prefix}style.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header role="banner">
    <h1>{html.escape(title)}</h1>
    <nav aria-label="Documentation Navigation">
{nav_html}
    </nav>
  </header>
  <main id="main-content" role="main">
{body_html}
  </main>
  <footer role="contentinfo">
    PyAudioGaming Official Documentation &mdash; Cross-Platform Audio Gaming for Windows, Linux, macOS, Android, iOS &amp; Web.
  </footer>
</body>
</html>
"""


def _render_params_table_html(entries, table_id):
	rows = []
	for e in entries:
		if e["params"]:
			param_lines = "<br>".join(
				f"<code>{html.escape(p['name'])}</code> ({html.escape(p['type'])}, default: <code>{html.escape(p['default'])}</code>)"
				for p in e["params"]
			)
		else:
			param_lines = "<em>None</em>"
		rows.append(
			f"    <tr>"
			f"<td><span class=\"badge\">{html.escape(e['kind'])}</span><code>{html.escape(e['name'])}({html.escape(e['signature'])})</code></td>"
			f"<td>{param_lines}</td>"
			f"<td><code>{html.escape(e['returns'])}</code></td>"
			f"<td>{html.escape(e['doc'] or '—')}</td>"
			f"</tr>"
		)
	return f"""<table class="api-tbl" id="{html.escape(table_id)}">
  <thead><tr><th>Symbol &amp; Signature</th><th>Parameters (Type &amp; Default)</th><th>Returns</th><th>Description</th></tr></thead>
  <tbody>
{chr(10).join(rows)}
  </tbody>
</table>"""


def build_all():
	for d in (HTML_DIR, HTML_MOD_DIR, TXT_DIR, TXT_MOD_DIR, CHM_DIR, REF_DIR, REF_MOD_DIR, EX_DIR):
		d.mkdir(parents=True, exist_ok=True)

	# Clean old monolithic files if any
	(HTML_DIR / "style.css").write_text(CSS, encoding="utf-8")

	# 1. Tutorial HTML pages
	for p in TUTORIAL_PAGES:
		(HTML_DIR / p["filename"]).write_text(
			_render_html(p["filename"], p["title"], p["body"], depth=0), encoding="utf-8"
		)

	# 2. Introspect every module and generate dedicated per-module HTML, TXT, CSV, JSON
	all_modules_meta = []
	hub_cards = []
	all_chm_files = [f"..\\html\\{p['filename']}" for p in TUTORIAL_PAGES] + ["..\\html\\api_reference.html", "..\\html\\style.css"]
	chm_index_entries = []

	for mod in TARGET_MODULES:
		meta = introspect_module(mod)
		guide = MODULE_GUIDES.get(mod, {"title": mod, "summary": "", "guide": ""})
		meta["title"] = guide["title"]
		meta["summary"] = guide["summary"]
		all_modules_meta.append(meta)

		# Flatten rows for this module's CSV / JSON / TXT
		flat_rows = []
		for fn in meta["functions"]:
			flat_rows.append((mod, "module", fn["kind"], fn["name"], fn["signature"], fn["returns"], fn["doc"]))
			chm_index_entries.append((f"{mod}.{fn['name']}", f"..\\html\\modules\\{mod}.html"))
		for cls in meta["classes"]:
			chm_index_entries.append((f"{mod}.{cls['name']}", f"..\\html\\modules\\{mod}.html"))
			for m in cls["methods"]:
				flat_rows.append((mod, cls["name"], m["kind"], f"{cls['name']}.{m['name']}", m["signature"], m["returns"], m["doc"]))
				chm_index_entries.append((f"{cls['name']}.{m['name']} ({mod})", f"..\\html\\modules\\{mod}.html"))

		# --- Per-module CSV ---
		with open(REF_MOD_DIR / f"{mod}.csv", "w", encoding="utf-8-sig", newline="") as cf:
			w = csv.writer(cf)
			w.writerow(["Module", "Owner", "Kind", "Symbol", "Parameters", "Returns", "Description"])
			for r in flat_rows:
				w.writerow(r)

		# --- Per-module JSON ---
		(REF_MOD_DIR / f"{mod}.json").write_text(
			json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
		)

		# --- Per-module TXT ---
		txt_lines = [
			"=" * 72,
			f"MODULE: pyaudiogaming.{mod}",
			guide["title"],
			"=" * 72,
			"",
			"SUMMARY:",
			guide["summary"],
			"",
		]
		if meta["functions"]:
			txt_lines.append("[MODULE FUNCTIONS]\n" + "-" * 40)
			for fn in meta["functions"]:
				txt_lines.append(f"* {fn['name']}({fn['signature']}) -> {fn['returns']}")
				if fn["doc"]:
					txt_lines.append(f"  {fn['doc']}")
		for cls in meta["classes"]:
			txt_lines.append(f"\n[CLASS {cls['name']}]\n" + "-" * 40)
			if cls["doc"]:
				txt_lines.append(cls["doc"])
			for m in cls["methods"]:
				txt_lines.append(f"* {cls['name']}.{m['name']}({m['signature']}) -> {m['returns']} [{m['kind']}]")
				if m["doc"]:
					txt_lines.append(f"  {m['doc']}")
		(TXT_MOD_DIR / f"{mod}.txt").write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

		# --- Per-module HTML ---
		sections = [
			f'<p><a href="../api_reference.html">&larr; Back to All Modules</a></p>',
			f'<div class="callout"><strong>Summary:</strong> {html.escape(guide["summary"])}</div>',
			f'<h2>Usage Guide &amp; Examples</h2>\n{guide["guide"]}',
			'<h2>Parameter &amp; API Tables</h2>',
			'<label for="mod-search">Filter symbols in this module:</label>',
			'<input id="mod-search" type="search" placeholder="Type method or parameter name..." oninput="filterMod(this.value)">',
		]
		if meta["functions"]:
			sections.append("<h3>Module-Level Functions</h3>")
			sections.append(_render_params_table_html(meta["functions"], f"tbl_{mod}_funcs"))
		for cls in meta["classes"]:
			sections.append(f"<h3>Class <code>{html.escape(cls['name'])}</code></h3>")
			if cls["doc"]:
				sections.append(f"<p>{html.escape(cls['doc'])}</p>")
			if cls["methods"]:
				sections.append(_render_params_table_html(cls["methods"], f"tbl_{mod}_{cls['name']}"))

		sections.append("""<script>
function filterMod(q) {
  q = (q || '').toLowerCase();
  var rows = document.querySelectorAll('.api-tbl tbody tr');
  for (var i = 0; i < rows.length; i++) {
    rows[i].style.display = rows[i].innerText.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
  }
}
</script>""")

		(HTML_MOD_DIR / f"{mod}.html").write_text(
			_render_html(f"{mod}.html", f"{guide['title']} — PyAudioGaming", "\n".join(sections), depth=1),
			encoding="utf-8",
		)
		all_chm_files.append(f"..\\html\\modules\\{mod}.html")

		total_syms = len(meta["functions"]) + sum(len(c["methods"]) for c in meta["classes"])
		hub_cards.append(
			f'  <div class="card">'
			f'<h3><a href="modules/{mod}.html">pyaudiogaming.{mod}</a></h3>'
			f'<div><span class="badge">{len(meta["classes"])} classes</span><span class="badge">{total_syms} APIs</span></div>'
			f'<p>{html.escape(guide["summary"])}</p>'
			f'</div>'
		)

	# 3. Module Reference Hub (api_reference.html)
	hub_body = f"""
<h2>Per-Module API &amp; Parameter Reference Hub</h2>
<p>Each module has its own dedicated page with complete usage guides, code examples, and cleanly split parameter tables. Separate CSV/JSON/TXT files per module are also available in <code>docs/reference/modules/</code> and <code>docs/txt/modules/</code>.</p>
<label for="hub-search">Filter modules:</label>
<input id="hub-search" type="search" placeholder="Search module name or topic (e.g. audio, gui, timer, storage)..." oninput="filterHub(this.value)">
<div class="grid" id="mod-grid">
{chr(10).join(hub_cards)}
</div>
<script>
function filterHub(q) {{
  q = (q || '').toLowerCase();
  var cards = document.querySelectorAll('#mod-grid .card');
  for (var i = 0; i < cards.length; i++) {{
    cards[i].style.display = cards[i].innerText.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
  }}
}}
</script>
"""
	(HTML_DIR / "api_reference.html").write_text(
		_render_html("api_reference.html", "Module Reference Hub — PyAudioGaming", hub_body, depth=0),
		encoding="utf-8",
	)

	# 4. Top-level TXT guides & index
	(TXT_DIR / "README.txt").write_text(
		"====================================================================\n"
		"PYAUDIOGAMING — COMPLETE ENGLISH DOCUMENTATION SUITE\n"
		"====================================================================\n\n"
		"- docs/html/index.html                : Main HTML5 Documentation\n"
		"- docs/html/modules/<module>.html     : Dedicated page & parameter table per module\n"
		"- docs/txt/modules/<module>.txt       : Dedicated plain-text reference per module\n"
		"- docs/reference/modules/<module>.csv : Separate Excel/CSV parameter table per module\n"
		"- docs/reference/modules/<module>.json: Separate JSON schema per module\n"
		"- docs/examples/*.py                  : Runnable Python examples\n"
		"- docs/chm/                           : Microsoft HTML Help (.chm) project\n",
		encoding="utf-8",
	)
	guide_parts = ["PYAUDIOGAMING — COMPLETE GUIDE (BEGINNER TO ADVANCED)\n" + "=" * 68 + "\n"]
	for p in TUTORIAL_PAGES:
		txt = html.unescape(re.sub(r"<[^>]+>", "", p["body"]))
		txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
		guide_parts.append(f"\n{'=' * 68}\n{p['title']}\n{'=' * 68}\n{txt}\n")
	(TXT_DIR / "GUIDE_BEGINNER_TO_ADVANCED.txt").write_text("\n".join(guide_parts), encoding="utf-8")

	# 5. Examples
	for fname, code in EXAMPLES.items():
		(EX_DIR / fname).write_text(code, encoding="utf-8")

	# 6. CHM project with nested Module Reference tree
	hhp = (
		"[OPTIONS]\nCompatibility=1.1 or later\nCompiled file=pyaudiogaming.chm\n"
		"Contents file=toc.hhc\nDefault topic=..\\html\\index.html\nDisplay compile progress=Yes\n"
		"Full-text search=Yes\nIndex file=index.hhk\nLanguage=0x409 English (United States)\n"
		"Title=PyAudioGaming Official Documentation\n\n[FILES]\n"
		+ "\n".join(all_chm_files) + "\n"
	)
	(CHM_DIR / "pyaudiogaming.hhp").write_text(hhp, encoding="utf-8")

	tut_toc = "\n".join(
		f'    <LI><OBJECT type="text/sitemap"><param name="Name" value="{html.escape(p["nav"])}">'
		f'<param name="Local" value="..\\html\\{p["filename"]}"></OBJECT>'
		for p in TUTORIAL_PAGES
	)
	mod_toc = "\n".join(
		f'    <LI><OBJECT type="text/sitemap"><param name="Name" value="pyaudiogaming.{mod}">'
		f'<param name="Local" value="..\\html\\modules\\{mod}.html"></OBJECT>'
		for mod in TARGET_MODULES
	)
	hhc = f"""<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN">
<HTML><BODY>
<UL>
  <LI><OBJECT type="text/sitemap"><param name="Name" value="Tutorials (Beginner to Advanced)"></OBJECT>
  <UL>
{tut_toc}
  </UL>
  <LI><OBJECT type="text/sitemap"><param name="Name" value="Per-Module Reference &amp; Parameter Tables"><param name="Local" value="..\\html\\api_reference.html"></OBJECT>
  <UL>
{mod_toc}
  </UL>
</UL>
</BODY></HTML>
"""
	(CHM_DIR / "toc.hhc").write_text(hhc, encoding="utf-8")

	hhk_items = "\n".join(
		f'  <LI><OBJECT type="text/sitemap"><param name="Name" value="{html.escape(name)}">'
		f'<param name="Local" value="{local}"></OBJECT>'
		for name, local in chm_index_entries
	)
	(CHM_DIR / "index.hhk").write_text(
		f'<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN">\n<HTML><BODY>\n<UL>\n{hhk_items}\n</UL>\n</BODY></HTML>\n',
		encoding="utf-8",
	)
	print(f"Generated full per-module English documentation for {len(TARGET_MODULES)} modules ({len(chm_index_entries)} indexed symbols)!")


if __name__ == "__main__":
	build_all()
