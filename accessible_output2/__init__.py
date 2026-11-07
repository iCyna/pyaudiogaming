from __future__ import absolute_import
import ctypes
import os
import types
import sys
import importlib.util
from pyaudiogaming import system

def load_library(name,  	cdll=False):
	return system.load_dll(name, WinDLL=not cdll)

def get_output_classes():
    from . import outputs

    module_type = types.ModuleType
    classes = [
        m.output_class
        for m in outputs.__dict__.values()
        if isinstance(m, module_type) and hasattr(m, "output_class")
    ]
    return sorted(classes, key=lambda c: c.priority)

def find_datafiles():
    from pathlib import Path
    root = Path(system.module_path()) / "lib" / system.get_arch_dir()
    files = [str(path) for path in root.glob("*" + system.get_ext())]
    return [(str(Path("lib") / system.get_arch_dir()), files)] if files else []
