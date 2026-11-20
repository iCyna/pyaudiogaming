from __future__ import absolute_import
import pyaudiogaming.accessible_output2
from .base import Output, OutputError
from time import monotonic


class Auto(Output):
    """An output which automatically selects the first available output on the system"""
    def __init__(self):
        output_classes = pyaudiogaming.accessible_output2.get_output_classes()
        self.outputs = []
        self.errors = {}
        self._selected = None
        self._forced_output = None
        self._next_probe = 0.0
        for output in output_classes:
            try:
                self.outputs.append(output())
            except (OutputError, OSError, ImportError, RuntimeError, AttributeError) as error:
                self.errors[output.name] = str(error);print(self.outputs)

    def get_outputs(self, active_only=False):
        names = []
        for output in self.outputs:
            if active_only:
                try:
                    if not output.is_active():
                        continue
                except (OSError, RuntimeError, AttributeError):
                    continue
            names.append(output.name)
        return names

    def get_output(self):
        if self._forced_output is not None:
            return self._forced_output.name
        return "auto"

    def get_active_output(self):
        output = self.get_first_available_output()
        return output.name if output else None

    def set_output(self, name=None):
        if name is None or str(name).strip().lower() in ("", "auto"):
            self._forced_output = None
            self._selected = None
            self._next_probe = 0.0
            return True
        target = str(name).strip().lower()
        for output in self.outputs:
            if output is name or output.name.lower() == target or output.__class__.__name__.lower() == target:
                self._forced_output = output
                self._selected = output
                return True
        return False

    def get_first_available_output(self):
        """
        Finds the ffirst available output.
        This is automatically called in braille, output and speak.
        """
        if self._forced_output is not None:
            try:
                if self._forced_output.is_active():
                    return self._forced_output
            except (OSError, RuntimeError, AttributeError):
                pass
        now = monotonic()
        if self._selected is not None and now < self._next_probe:
            return self._selected
        self._selected = None
        self._next_probe = now + 0.25
        for output in self.outputs:
            try:
                if output.is_active():
                    self._selected = output
                    return output
            except (OSError, RuntimeError, AttributeError):
                continue
        return None

    def speak(self, *args, **kwargs):
        """
        Speaks the given text if the output supports speech

        Args:
          text (str): The text to speak.
          **options: Additional options.
        """
        output = self.get_first_available_output()
        if output:
            output.speak(*args, **kwargs)

    def silence(self):
        output = self.get_first_available_output()
        if output:
            if hasattr(output, "silence"):
                output.silence()

    def get_volume(self):
        output = self.get_first_available_output()
        if output and hasattr(output, 'get_volume'):
            return output.get_volume()
    def set_volume(self, volume):
        output = self.get_first_available_output()
        if output and hasattr(output, 'set_volume'):
            output.set_volume(volume)

    def get_rate(self):
        output = self.get_first_available_output()
        if output and hasattr(output, 'get_rate'):
            return output.get_rate()
        return None

    def set_rate(self, rate):
        output = self.get_first_available_output()
        if output and hasattr(output, 'set_rate'):
            output.set_rate(rate)

    def get_pitch(self):
        output = self.get_first_available_output()
        if output and hasattr(output, 'get_pitch'):
            return output.get_pitch()
        return None

    def set_pitch(self, pitch):
        output = self.get_first_available_output()
        if output and hasattr(output, 'set_pitch'):
            output.set_pitch(pitch)

    def get_voice(self):
        output = self.get_first_available_output()
        if output and hasattr(output, 'get_voice'):
            return output.get_voice()
        return None

    def set_voice(self, voice):
        output = self.get_first_available_output()
        if output and hasattr(output, 'set_voice'):
            output.set_voice(voice)

    def list_voices(self):
        output = self.get_first_available_output()
        if output and hasattr(output, 'list_voices'):
            try:
                return list(output.list_voices())
            except Exception:
                return []
        return []

    def get_capabilities(self):
        output = self.get_first_available_output()
        if not output:
            return {}
        return {
            "name": output.name,
            "has_rate": bool(getattr(output, "has_rate", False) and hasattr(output, "set_rate")),
            "has_pitch": bool(getattr(output, "has_pitch", False) and hasattr(output, "set_pitch")),
            "has_volume": bool(getattr(output, "has_volume", False) and hasattr(output, "set_volume")),
            "has_pan": bool(getattr(output, "has_pan", False) and hasattr(output, "set_pan")),
            "has_mono": bool(getattr(output, "has_mono", False) and hasattr(output, "set_mono")),
            "has_hrtf": bool(getattr(output, "has_hrtf", False) and hasattr(output, "set_hrtf")),
            "has_fx": bool(getattr(output, "has_fx", False) and hasattr(output, "set_fx")),
            "has_auto_pause": bool(getattr(output, "has_auto_pause", False) and hasattr(output, "set_auto_pause")),
            "has_output_device": bool(hasattr(output, "set_output_device")),
            "has_voice": bool(hasattr(output, "list_voices") and hasattr(output, "set_voice")),
            "min_rate": getattr(output, "min_rate", -10),
            "max_rate": getattr(output, "max_rate", 10),
            "min_pitch": getattr(output, "min_pitch", -10),
            "max_pitch": getattr(output, "max_pitch", 10),
            "min_volume": getattr(output, "min_volume", 0),
            "max_volume": getattr(output, "max_volume", 100),
            "min_pan": getattr(output, "min_pan", -100),
            "max_pan": getattr(output, "max_pan", 100),
        }

    def get_pan(self):
        output = self.get_first_available_output()
        if output and hasattr(output, "get_pan"):
            return output.get_pan()
        return None

    def set_pan(self, value):
        output = self.get_first_available_output()
        if output and hasattr(output, "set_pan"):
            output.set_pan(value)

    def get_sound_pitch(self):
        output = self.get_first_available_output()
        if output and hasattr(output, "get_sound_pitch"):
            return output.get_sound_pitch()
        return None

    def set_sound_pitch(self, value):
        output = self.get_first_available_output()
        if output and hasattr(output, "set_sound_pitch"):
            output.set_sound_pitch(value)

    def get_output_device(self):
        output = self.get_first_available_output()
        if output and hasattr(output, "get_output_device"):
            return output.get_output_device()
        return -1

    def set_output_device(self, device):
        output = self.get_first_available_output()
        if output and hasattr(output, "set_output_device"):
            output.set_output_device(device)

    def get_sound(self):
        output = self.get_first_available_output()
        if output and hasattr(output, "get_sound"):
            return output.get_sound()
        return None

    def get_mono(self):
        output = self.get_first_available_output()
        return output.get_mono() if output and hasattr(output, "get_mono") else False

    def set_mono(self, value):
        output = self.get_first_available_output()
        if output and hasattr(output, "set_mono"):
            output.set_mono(value)

    def get_hrtf(self):
        output = self.get_first_available_output()
        return output.get_hrtf() if output and hasattr(output, "get_hrtf") else False

    def set_hrtf(self, value):
        output = self.get_first_available_output()
        if output and hasattr(output, "set_hrtf"):
            output.set_hrtf(value)

    def get_fx(self):
        output = self.get_first_available_output()
        return output.get_fx() if output and hasattr(output, "get_fx") else None

    def set_fx(self, value):
        output = self.get_first_available_output()
        if output and hasattr(output, "set_fx"):
            output.set_fx(value)

    def set_zone_fx_provider(self, provider):
        for output in self.outputs:
            if hasattr(output, "set_zone_fx_provider"):
                output.set_zone_fx_provider(provider)

    def list_fx(self):
        output = self.get_first_available_output()
        if output and hasattr(output, "list_fx"):
            return list(output.list_fx())
        return []

    def get_auto_pause(self):
        output = self.get_first_available_output()
        return output.get_auto_pause() if output and hasattr(output, "get_auto_pause") else False

    def set_auto_pause(self, enabled):
        output = self.get_first_available_output()
        if output and hasattr(output, "set_auto_pause"):
            output.set_auto_pause(enabled)

    def speak3d(self, text, lx, ly, lz, sx, sy, sz, interrupt=True, **kwargs):
        output = self.get_first_available_output()
        if not output:
            return
        if getattr(output, "has_hrtf", False):
            output.speak(text, interrupt=interrupt, pos3d=(lx, ly, lz, sx, sy, sz, kwargs))
        else:
            output.speak(text, interrupt=interrupt)
    def braille(self, *args, **kwargs):
        """
        Brailles the given text if the output supports Braille

        Args:
          text (str): The text to braille.
          **options: Additional options.
        """
        output = self.get_first_available_output()
        if output:
            output.braille(*args, **kwargs)

    def output(self, *args, **kwargs):
        output = self.get_first_available_output()
        if output:
            output.speak(*args, **kwargs)

    def is_system_output(self):
        """Returns True if this output is a system output."""
        output = self.get_first_available_output()
        if output:
            return output.is_system_output()

    def call(self, name_functions, *args, **kwargs):
        output = self.get_first_available_output()

        if not output or not hasattr(output, name_functions): return None
        func = getattr(output, name_functions)
        if callable(func):
            return func(*args, **kwargs)
        return None