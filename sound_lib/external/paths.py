import os
import sys

def is_frozen():
    """Kiểm tra xem chương trình có đang chạy trong môi trường đóng gói (frozen) không."""
    return hasattr(sys, "frozen")

def embedded_data_path():
    """Trả về đường dẫn của file thực thi trong môi trường đóng gói (frozen)."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)

def module_path():
    """Trả về đường dẫn của thư mục module hiện tại khi không ở chế độ đóng gói."""
    return os.path.dirname(__file__)

# Sử dụng các hàm thay thế platform_utils
if is_frozen():
    x86_path = os.path.join(embedded_data_path(), 'sound_lib', 'lib', 'x86')
    x64_path = os.path.join(embedded_data_path(), 'sound_lib', 'lib', 'x64')
else:
    x86_path = os.path.join(module_path(), '..', 'lib', 'x86')
    x64_path = os.path.join(module_path(), '..', 'lib', 'x64')
