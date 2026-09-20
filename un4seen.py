import os
import zipfile
import shutil

def extract_all_basses():
    base_dir = "basses"
    lib_dir = "lib"
    
    if not os.path.exists(base_dir):
        print(f"Không tìm thấy thư mục {base_dir}")
        return

    # Quét tất cả file zip trong thư mục basses
    for filename in os.listdir(base_dir):
        if not filename.endswith(".zip"):
            continue
            
        zpath = os.path.join(base_dir, filename)
        lname = filename.lower()
        print(f"\n📦 Đang xử lý kiện hàng: {filename}")
        
        with zipfile.ZipFile(zpath, 'r') as z:
            files = z.namelist()
            
            # ==========================================
            # 1. WINDOWS (Không có hậu tố OS ở tên file)
            # ==========================================
            if not any(x in lname for x in ["-linux", "-osx", "-macos", "-android", "-ios"]):
                for f in files:
                    if not f.lower().endswith(".dll"): continue
                    basename = os.path.basename(f)
                    
                    if "/" not in f:  # Nằm ở root -> x86
                        extract_file(z, f, os.path.join(lib_dir, "x86", basename))
                    elif f.startswith("x64/"):
                        extract_file(z, f, os.path.join(lib_dir, "x64", basename))
            
            # ==========================================
            # 2. LINUX
            # ==========================================
            elif "-linux" in lname:
                for f in files:
                    if not f.lower().endswith(".so"): continue
                    basename = os.path.basename(f)
                    
                    if f.startswith("libs/aarch64/"):
                        extract_file(z, f, os.path.join(lib_dir, "aarch64", basename))
                    elif f.startswith("libs/armhf/"):
                        extract_file(z, f, os.path.join(lib_dir, "armhf", basename))
                    elif f.startswith("x64/"):
                        extract_file(z, f, os.path.join(lib_dir, "x64", basename))
                    elif "/" not in f:  # Nằm ở root -> x86
                        extract_file(z, f, os.path.join(lib_dir, "x86", basename))
                        
            # ==========================================
            # 3. MACOS
            # ==========================================
            elif "-osx" in lname or "-macos" in lname:
                for f in files:
                    if not f.lower().endswith(".dylib"): continue
                    basename = os.path.basename(f)
                    
                    # Mac chỉ có 1 file dylib (Universal) -> Dồn vô x64 và x86 luôn cho đủ
                    extract_file(z, f, os.path.join(lib_dir, "x64", basename))
                    extract_file(z, f, os.path.join(lib_dir, "x86", basename))
                    
            # ==========================================
            # 4. IOS & IOSIMULATOR
            # ==========================================
            elif "-ios" in lname:
                for f in files:
                    # Bỏ qua thư mục trống và file header .h
                    if f.endswith("/") or f.endswith(".h"): continue
                    
                    basename = os.path.basename(f)
                    
                    # Định vị file binary lõi bên trong xcframework (file này không có extension)
                    # Mẫu: bassloud.xcframework/ios-arm64_armv7_armv7s/bassloud.framework/bassloud
                    if ".xcframework/" in f and f.endswith(f".framework/{basename}"):
                        new_name = f"{basename}.so" # Đổi về chuẩn .so theo ý bạn
                        
                        if "simulator" in f.lower():
                            extract_file(z, f, os.path.join(lib_dir, "iosimulator", new_name))
                        else:
                            extract_file(z, f, os.path.join(lib_dir, "ios", new_name))
                            
            # ==========================================
            # 5. ANDROID
            # ==========================================
            elif "-android" in lname:
                for f in files:
                    if not f.lower().endswith(".so"): continue
                    basename = os.path.basename(f)
                    
                    if f.startswith("libs/"):
                        parts = f.split('/')
                        if len(parts) >= 3:
                            # Tự động bắt lấy tên thư mục kiến trúc gốc (x86_64, x86, arm64-v8a, armeabi-v7a)
                            abi = parts[1] 
                            extract_file(z, f, os.path.join(lib_dir, "android", abi, basename))

def extract_file(z, src, dest):
    # Tạo sẵn các thư mục cha nếu chưa có (x64, armhf, android/arm64-v8a...)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with z.open(src) as s, open(dest, 'wb') as d:
        shutil.copyfileobj(s, d)
    print(f"  -> Đã giao: {dest}")

if __name__ == "__main__":
    extract_all_basses()