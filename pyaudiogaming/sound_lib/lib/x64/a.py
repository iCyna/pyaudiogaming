import ctypes
import os

# Tải thư viện BASS (bạn cần bass.dll trong thư mục dự án)
bass = ctypes.WinDLL(os.path.abspath("bass.dll"))

# Khởi tạo BASS và bật chế độ 3D
if not bass.BASS_Init(-1, 44100, 0, 0, 0):
    print("BASS initialization error!")

# Đặt vị trí người nghe và hướng
def set_listener_position(x, y, z, front_x, front_y, front_z, top_x, top_y, top_z):
    pos = ctypes.c_float * 3
    bass.BASS_Set3DPosition(
        pos(x, y, z),            # Position of listener
        pos(front_x, front_y, front_z),  # Direction listener is facing
        pos(top_x, top_y, top_z) # Up direction
    )

# Tải âm thanh 3D
def load_3d_sound(filename):
    handle = bass.BASS_StreamCreateFile(False, filename.encode(), 0, 0, ctypes.c_uint(0x400000))  # BASS_SAMPLE_3D
    if not handle:
        print("Error loading sound:", filename)
        return None

    # Thiết lập các thuộc tính 3D của âm thanh
    bass.BASS_ChannelSet3DAttributes(handle, 0, -1, -1, -1, -1, -1)
    return handle

# Đặt vị trí âm thanh
def set_sound_position(handle, x, y, z):
    pos = ctypes.c_float * 3
    bass.BASS_ChannelSet3DPosition(handle, pos(x, y, z), None, None)

# Phát âm thanh 3D
def play_3d_sound(handle):
    bass.BASS_ChannelPlay(handle, False)

# Khởi tạo vị trí người nghe
set_listener_position(0, 0, 0, 0, 0, 1, 0, 1, 0)

# Tạo và phát âm thanh 3D
sound_handle = load_3d_sound("music.ogg")
if sound_handle:
    set_sound_position(sound_handle, 10, 0, 0)  # Vị trí nguồn âm thanh
    play_3d_sound(sound_handle)

# Cập nhật môi trường 3D
bass.BASS_Apply3D()
