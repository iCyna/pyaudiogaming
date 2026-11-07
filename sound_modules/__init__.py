"""Register bundled codecs; load feature add-ons on demand."""
import importlib
import logging
from .. import system

CODECS = {
    "windows": ("pybassopus", "pybassflac", "pybasswma", "pybass_aac", "pybass_alac", "pybassmpc"),
    "linux": ("pybassopus", "pybassflac", "pybassmpc"),
    "macos": ("pybassopus", "pybassflac", "pybass_aac", "pybassmpc"),
    "android": ("pybassopus", "pybassflac", "pybass_aac", "pybass_alac", "pybassmpc"),
    "ios": ("pybassopus", "pybassflac", "pybassmpc"),
}
errors = {}
for _name in CODECS.get(system.get_platform()["os"], ()):
    try:
        importlib.import_module("." + _name, __name__)
    except (OSError, AttributeError, ImportError) as _error:
        errors[_name] = str(_error)
        logging.getLogger(__name__).debug("Optional codec %s: %s", _name, _error)
