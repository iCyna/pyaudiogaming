from __future__ import absolute_import
import ctypes
import os
import types
import sys
import importlib.util

def is_frozen():
    """Kiểm tra xem mã có đang chạy trong môi trường frozen (đóng gói) hay không."""
    return hasattr(sys, "frozen")

def embedded_data_path():
    """Lấy đường dẫn dữ liệu nhúng trong môi trường đóng gói (frozen)"""
    if is_frozen():
        return os.path.dirname(sys.executable)  # Đường dẫn của file thực thi đóng gói
    return os.path.dirname(__file__)  # Đường dẫn của module hiện tại

def module_path():
    """Lấy đường dẫn module hiện tại khi không ở môi trường đóng gói"""
    return os.path.dirname(__file__)

def load_library(libname, cdll=False):
    if is_frozen():
        libfile = os.path.join(
            embedded_data_path(), "accessible_output2", "lib", libname
        )
    else:
        libfile = os.path.join(module_path(), "lib", libname)
    if not os.path.exists(libfile):
        _cxfreeze_libfile = os.path.join(
            embedded_data_path(), "lib", "accessible_output2", "lib", libname
        )
        if os.path.exists(_cxfreeze_libfile):
            libfile = _cxfreeze_libfile
    if cdll:
        return ctypes.cdll[libfile]
    return ctypes.windll[libfile]

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
    import platform
    from glob import glob
    import accessible_output2

    if platform.system() != "Windows":
        return []
    path = os.path.join(accessible_output2.__path__[0], "lib", "*.dll")
    results = glob(path)
    dest_dir = os.path.join("accessible_output2", "lib")
    return [(dest_dir, results)]
