# -*- coding: utf-8 -*-
# app build tool (Unified Desktop & Android BeeWare Builder)
# Idea from Yukio Nozawa and continue edit and fix by ihcyna(Labubu)

import os
import sys
import re
import shutil
import glob
import ast
import sysconfig
import subprocess
from pathlib import Path

# Chặn đứng ngay lập tức nếu tiến trình con của Briefcase/Gradle vô tình gọi ngược vào file này
if os.environ.get("PYAG_BUILDING_ANDROID") == "1":
	if __name__ == "__main__":
		sys.exit(0)

try:
	from pyaudiogaming import utils as common
	from pyaudiogaming.file import *
	from pyaudiogaming import system as sys_checker
except ImportError:
	sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
	from pyaudiogaming import utils as common
	from pyaudiogaming.file import *
	from pyaudiogaming import system as sys_checker


# ==============================================================================
# PHẦN 1: ANDROID BEEWARE (BRIEFCASE) BUILDER (Tích hợp từ android_build.py)
# ==============================================================================

ROOT = Path(__file__).resolve().parent
ABIS = {"arm64-v8a", "armeabi-v7a", "x86", "x86_64"}

# Thư mục chứa Toolchain di động (SDK, NDK, JDK, Gradle dùng chung cho mọi dự án)
PORTABLE_HOME = ROOT / "include" / "android" / "toolchain"

# Danh sách các file trình biên dịch cần loại trừ tuyệt đối khi copy vào project Android
EXCLUDE_BUILD_FILES = {
	"compile.py", "compile_2.py", "builder.py", "android_build.py", "setup.py"
}


def _save_text(content, path):
	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(str(content), encoding="utf-8")


def _load_text(path):
	return Path(path).read_text(encoding="utf-8")


def _find_real_python():
	"""Tìm python.exe thật để tránh trường hợp sys.executable đang trỏ vào file .exe đã đóng gói của compile.py."""
	exe = Path(sys.executable).resolve()
	if exe.stem.lower().startswith("python"):
		return str(exe)

	for cand in ("python", "python3", "py"):
		found = shutil.which(cand)
		if found and Path(found).resolve() != exe:
			return found

	base_py = Path(sys.base_prefix) / "python.exe"
	if base_py.exists():
		return str(base_py)

	return str(exe)


def _get_portable_env():
	PORTABLE_HOME.mkdir(parents=True, exist_ok=True)
	gradle_home = PORTABLE_HOME / "gradle_cache"
	gradle_home.mkdir(parents=True, exist_ok=True)

	env = os.environ.copy()
	env.pop("PYTHONPATH", None)
	env.pop("PYTHONHOME", None)
	env.pop("PYTHONSTARTUP", None)
	env["PYTHONNOUSERSITE"] = "1"
	env["PYTHONUTF8"] = "1"
	env["PYTHONIOENCODING"] = "utf-8"
	env["BRIEFCASE_HOME"] = str(PORTABLE_HOME)
	env["GRADLE_USER_HOME"] = str(gradle_home)
	env["PYAG_BUILDING_ANDROID"] = "1"
	return env


def _ensure_briefcase(env=None):
	run_env = env or _get_portable_env()
	py_exe = _find_real_python()
	try:
		subprocess.run(
			[py_exe, "-I", "-m", "briefcase", "--version"],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			env=run_env,
			check=True
		)
	except (subprocess.CalledProcessError, FileNotFoundError):
		print("[BeeWare] Installing Briefcase automatically...")
		subprocess.run(
			[py_exe, "-I", "-m", "pip", "install", "briefcase"],
			env=run_env,
			check=True
		)


def _run_briefcase(args_list, cwd, env):
	py_exe = _find_real_python()
	# Chạy với cờ -I (Isolated Mode) để cô lập hoàn toàn khỏi thư mục hiện tại và tránh gọi nhầm compile.py
	cmd = [py_exe, "-I", "-m", "briefcase"] + list(args_list)
	res = subprocess.run(cmd, cwd=cwd, env=env)
	if res.returncode != 0:
		raise RuntimeError(
			f"Briefcase failed at command: briefcase {' '.join(args_list)} (exit code {res.returncode})"
		)


def _normalize_abis(arch=None):
	raw = arch if isinstance(arch, list) else [arch or "arm64-v8a"]
	aliases = {
		"a64": "arm64-v8a",
		"arm64": "arm64-v8a",
		"aarch64": "arm64-v8a",
		"arm": "armeabi-v7a",
		"armv7": "armeabi-v7a",
		"a86": "x86",
		"x64": "x86_64"
	}
	abis = []
	for a in raw:
		if not a or str(a).lower() in ("null", "none", "auto"):
			abis.append("arm64-v8a")
		else:
			abis.append(aliases.get(str(a).lower().strip(), str(a).strip()))
	abis = list(dict.fromkeys(abis))
	if any(a not in ABIS for a in abis):
		raise ValueError(f"Unsupported Android ABI: {abis}")
	return abis


def _collect_and_verify_libs(abis, app_root, staging_native_dir, package_lib_dir):
	if staging_native_dir.exists():
		shutil.rmtree(staging_native_dir)
	staging_native_dir.mkdir(parents=True, exist_ok=True)

	for abi in abis:
		src_dirs = [
			ROOT / "lib" / abi,
			app_root / "lib" / abi,
			app_root / "pyaudiogaming" / "lib" / abi
		]
		target_jni = staging_native_dir / abi
		target_pkg = package_lib_dir / abi
		target_jni.mkdir(parents=True, exist_ok=True)
		target_pkg.mkdir(parents=True, exist_ok=True)

		copied_files = set()
		for sdir in src_dirs:
			if not sdir.is_dir():
				continue
			for so_file in sdir.glob("*.so"):
				fname = so_file.name
				lib_fname = fname if fname.startswith("lib") else f"lib{fname}"
				shutil.copy2(so_file, target_jni / lib_fname)
				shutil.copy2(so_file, target_pkg / lib_fname)
				copied_files.add(lib_fname)

		for required in ("libbass.so", "libbassmix.so", "libbass_fx.so"):
			if required not in copied_files:
				raise ValueError(
					f"Missing required Android library '{required}' for ABI '{abi}'. "
					f"Expected inside: {ROOT / 'lib' / abi}"
				)


def _inject_gradle_jnilibs(workspace, slug, staging_native_dir, abis):
	gradle_app_dir = workspace / "build" / slug / "android" / "gradle" / "app"
	if not gradle_app_dir.exists():
		raise RuntimeError(f"Gradle project directory not found at: {gradle_app_dir}")

	jni_libs_dir = gradle_app_dir / "src" / "main" / "jniLibs"
	if jni_libs_dir.exists():
		shutil.rmtree(jni_libs_dir)
	jni_libs_dir.mkdir(parents=True, exist_ok=True)

	for abi in abis:
		src_abi = staging_native_dir / abi
		dst_abi = jni_libs_dir / abi
		if src_abi.is_dir():
			shutil.copytree(src_abi, dst_abi, dirs_exist_ok=True)
			so_list = [p.name for p in dst_abi.glob("*.so")]
			print(f"[BeeWare] Injected {len(so_list)} native libraries into jniLibs/{abi}: {', '.join(so_list)}")

	build_gradle_path = gradle_app_dir / "build.gradle"
	if build_gradle_path.exists():
		gradle_text = _load_text(build_gradle_path)
		marker = "// [PYAUDIOGAMING_JNILIBS_PATCH]"
		if marker not in gradle_text:
			abi_filters = ", ".join(f'"{a}"' for a in abis)
			patch_block = f"""
{marker}
android {{
    defaultConfig {{
        ndk {{
            abiFilters {abi_filters}
        }}
    }}
    packagingOptions {{
        jniLibs {{
            useLegacyPackaging true
        }}
    }}
}}
"""
			_save_text(gradle_text + "\n" + patch_block, build_gradle_path)


def prepare_android(project, name, data=(), arch=None, extra_reqs=()):
	entry = Path(str(project) + ".py").resolve()
	if not entry.is_file():
		raise ValueError(f"Entry script does not exist: {entry}")

	abis = _normalize_abis(arch)
	slug = re.sub(r"[^a-z0-9_]", "", str(name).lower().replace(" ", "_"))
	slug = re.sub(r"_+", "_", slug).strip("_")
	if not slug or not slug[0].isalpha():
		slug = "app_" + slug
	if any(c in str(name) for c in "\r\n"):
		raise ValueError("Application name must be a single line")

	workspace = ROOT / "include" / "android" / "projects" / slug
	app_src = workspace / "src" / slug

	if app_src.exists():
		shutil.rmtree(app_src)
	app_src.mkdir(parents=True, exist_ok=True)

	package = app_src / "pyaudiogaming"
	package.mkdir(parents=True, exist_ok=True)
	for item in ROOT.glob("*.py"):
		if item.name.lower() not in EXCLUDE_BUILD_FILES and not item.name.lower().startswith("compile"):
			shutil.copy2(item, package / item.name)

	for folder in ("sound_modules", "accessible_output2", "include", "utils"):
		src_folder = ROOT / folder
		if src_folder.is_dir():
			ignore_fn = shutil.ignore_patterns("__pycache__", "*.pyc", "desktop.ini", "android", "compile*.py", "android_build.py", "builder.py")
			shutil.copytree(src_folder, package / folder, dirs_exist_ok=True, ignore=ignore_fn)

	app_root = entry.parent
	for item in app_root.iterdir():
		if item.is_file() and item.suffix == ".py" and item.name.lower() not in EXCLUDE_BUILD_FILES and not item.name.lower().startswith("compile"):
			shutil.copy2(item, app_src / item.name)
		elif item.is_dir() and (item / "__init__.py").exists() and item.resolve() != ROOT and item.name.lower() != "pyaudiogaming":
			shutil.copytree(
				item,
				app_src / item.name,
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "desktop.ini", "compile*.py", "android_build.py", "builder.py")
			)

	shutil.copy2(entry, app_src / "main.py")

	_save_text("# Auto-generated package init\n", app_src / "__init__.py")
	bootstrap_code = """# -*- coding: utf-8 -*-
import os
import sys

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
try:
    os.chdir(_APP_DIR)
except Exception:
    pass

try:
    from pyaudiogaming import system as _sys_chk
    if _sys_chk.get_platform().get("os") == "android":
        for _core_lib in ("libbass", "libbassmix", "libbass_fx"):
            try:
                _sys_chk.load_dll(_core_lib)
            except Exception as _e:
                print(f"[Bootstrap] Warning preloading {_core_lib}: {_e}")
except Exception:
    pass

import main
if hasattr(main, "main") and callable(main.main):
    main.main()
"""
	_save_text(bootstrap_code, app_src / "__main__.py")

	for value in (data or ()):
		relative = Path(value)
		if relative.is_absolute() or ".." in relative.parts:
			raise ValueError(f"Data must be a relative path inside the application: {value}")
		original = app_root / relative
		if not original.exists():
			original = Path(value).resolve()
		if not original.exists():
			raise ValueError(f"Missing application data: {original}")
		destination = app_src / relative
		if original.is_dir():
			shutil.copytree(original, destination, dirs_exist_ok=True)
		else:
			destination.parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(original, destination)

	staging_native_dir = workspace / "native_libs"
	package_lib_dir = package / "lib"
	_collect_and_verify_libs(abis, app_root, staging_native_dir, package_lib_dir)

	_save_text("MIT License\n", workspace / "LICENSE")

	default_reqs = ["pycryptodome", "cryptography"]
	for r in (extra_reqs or ()):
		r_clean = str(r).strip()
		if r_clean and not r_clean.startswith("-") and r_clean not in default_reqs:
			default_reqs.append(r_clean)

	req_formatted = ",\n    ".join(f'"{r}"' for r in default_reqs)
	safe_name = str(name).replace('"', '\\"')
	pyproject_content = f"""[build-system]
requires = ["briefcase"]

[tool.briefcase]
project_name = "{safe_name}"
bundle = "org.pyaudiogaming"
version = "0.1.0"
url = "https://pyaudiogaming.org"
license = "MIT"
license-files = ["LICENSE"]
author = "PyAudioGaming"
author_email = "dev@pyaudiogaming.org"

[tool.briefcase.app.{slug}]
formal_name = "{safe_name}"
description = "{safe_name} built with PyAudioGaming BeeWare Backend"
sources = ["src/{slug}"]
requires = [
    {req_formatted}
]

[tool.briefcase.app.{slug}.android]
requires = []
permission.INTERNET = true
permission.RECORD_AUDIO = true
permission.MODIFY_AUDIO_SETTINGS = true
permission.WAKE_LOCK = true
"""
	_save_text(pyproject_content, workspace / "pyproject.toml")
	return workspace, slug, abis, staging_native_dir, app_root


def build_android(project, name, data=(), arch=None, args=(), prepare_only=False, rename_file=None, out_dir=None):
	extra_reqs = [a for a in (args or ()) if not str(a).startswith("-")]
	clean_rebuild = "--clean" in (args or ()) or "--clean" in sys.argv

	workspace, slug, abis, staging_native_dir, app_root = prepare_android(
		project, name, data, arch, extra_reqs=extra_reqs
	)
	print(f"[BeeWare] Android workspace prepared: {workspace}")
	print(f"[BeeWare] Portable Toolchain location: {PORTABLE_HOME}")

	if prepare_only:
		return True

	env = _get_portable_env()
	_ensure_briefcase(env)

	gradle_project_dir = workspace / "build" / slug / "android" / "gradle"
	if clean_rebuild and (workspace / "build" / slug / "android").exists():
		print("[BeeWare] Cleaning previous Android build cache...")
		shutil.rmtree(workspace / "build" / slug / "android")

	if not gradle_project_dir.exists():
		if (workspace / "build" / slug / "android").exists():
			shutil.rmtree(workspace / "build" / slug / "android")
		print("[BeeWare] Step 1/4: Creating Android project template...")
		_run_briefcase(["create", "android", "--no-input"], cwd=workspace, env=env)
	else:
		print("[BeeWare] Step 1/4: Updating existing Android project sources...")
		_run_briefcase(["update", "android", "-r", "--no-input"], cwd=workspace, env=env)

	print("[BeeWare] Step 2/4: Embedding native .so libraries into Android jniLibs...")
	_inject_gradle_jnilibs(workspace, slug, staging_native_dir, abis)

	print("[BeeWare] Step 3/4: Building Android project via Gradle...")
	_run_briefcase(["build", "android", "--no-input"], cwd=workspace, env=env)

	print("[BeeWare] Step 4/4: Packaging standalone APK...")
	_run_briefcase(
		["package", "android", "--packaging-format", "apk", "--adhoc-sign", "--no-input"],
		cwd=workspace, env=env
	)

	found_apks = []
	for search_root in (workspace / "dist", gradle_project_dir / "app" / "build" / "outputs" / "apk"):
		if search_root.exists():
			found_apks.extend(search_root.rglob("*.apk"))

	if not found_apks:
		raise RuntimeError("Briefcase finished but no .apk file was found in outputs!")

	found_apks.sort(key=lambda p: p.stat().st_mtime, reverse=True)
	best_apk = found_apks[0]

	target_dist = Path(out_dir) if out_dir else (app_root / "dist" / str(name))
	target_dist.mkdir(parents=True, exist_ok=True)

	apk_base = rename_file if rename_file else slug
	if not str(apk_base).lower().endswith(".apk"):
		apk_base = f"{apk_base}.apk"

	final_apk_path = target_dist / apk_base
	shutil.copy2(best_apk, final_apk_path)

	print("=" * 60)
	print(f"[BeeWare] Standalone APK successfully generated:")
	print(f" -> {final_apk_path.resolve()}")
	print("=" * 60)
	return True


# ==============================================================================
# PHẦN 2: TRÌNH BIÊN DỊCH CHÍNH & CẤU HÌNH (compile.py)
# ==============================================================================

def parse_val(val):
	val = val.strip()
	if val.lower() in ("null", "none", ""):
		return None
	if val in ("1", "true", "True", "yes"):
		return True
	if val in ("0", "false", "False", "no"):
		return False
	if (val.startswith("[") and val.endswith("]")) or (val.startswith("(") and val.endswith(")")):
		try:
			parsed = ast.literal_eval(val)
			return [str(x).strip() for x in parsed]
		except Exception:
			content = val[1:-1].strip()
			if not content:
				return []
			return [x.strip().strip("'\"") for x in content.split(",") if x.strip()]
	if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
		return val[1:-1]
	return val


def get_target_lib_info(os_name, arch_override=None):
	os_name = os_name.lower()
	info = sys_checker.get_arch()
	bit = info.get("bit", 64)
	machine = info.get("machine", "").lower()

	ext_map = {
		"windows": ".dll",
		"linux": ".so",
		"android": ".so",
		"macos": ".dylib",
		"ios": ".dylib"
	}
	ext = ext_map.get(os_name, ".dll")
	arch_dirs = []

	if arch_override:
		if isinstance(arch_override, list):
			arch_dirs = arch_override
		else:
			arch_dirs = [str(arch_override)]
	else:
		if os_name == "windows":
			arch_dirs = ["x64" if bit == 64 else "x86"]
		elif os_name == "macos":
			arch_dirs = ["mac"]
		elif os_name == "linux":
			if "aarch64" in machine or "arm64" in machine:
				arch_dirs = ["aarch64"]
			elif "arm" in machine:
				arch_dirs = ["armhf"]
			else:
				arch_dirs = ["x64" if bit == 64 else "x86"]
		elif os_name == "android":
			arch_dirs = ["arm64-v8a", "armeabi-v7a", "a64", "a86", "aarch64", "x86", "x64"]
		elif os_name == "ios":
			arch_dirs = ["ios", "arm64"]

	return ext, arch_dirs


def copy_platform_libs(src_root, dst_root, target_os, arch_override=None):
	ext, arch_dirs = get_target_lib_info(target_os, arch_override)
	
	for folder in ["include", "utils"]:
		src_dir = os.path.join(src_root, folder)
		if os.path.exists(src_dir):
			shutil.copytree(
				src_dir,
				os.path.join(dst_root, folder),
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns("android", "__pycache__", "*.pyc")
			)

	src_lib = os.path.join(src_root, "lib")
	dst_lib = os.path.join(dst_root, "lib")
	if not os.path.exists(src_lib):
		return

	os.makedirs(dst_lib, exist_ok=True)

	for item in os.listdir(src_lib):
		s_item = os.path.join(src_lib, item)
		if os.path.isfile(s_item) and item.lower().endswith(ext):
			shutil.copy2(s_item, os.path.join(dst_lib, item))

	for sub in arch_dirs:
		s_sub = os.path.join(src_lib, sub)
		if os.path.exists(s_sub) and os.path.isdir(s_sub):
			d_sub = os.path.join(dst_lib, sub)
			os.makedirs(d_sub, exist_ok=True)
			for root, dirs, files in os.walk(s_sub):
				rel = os.path.relpath(root, s_sub)
				target_sub = os.path.join(d_sub, rel) if rel != "." else d_sub
				os.makedirs(target_sub, exist_ok=True)
				for file in files:
					if file.lower().endswith(ext):
						shutil.copy2(os.path.join(root, file), os.path.join(target_sub, file))


def dopackage(PROJECT, PROJECT_FULL_NAME, target_os="windows"):
	print(f"Creating installer/package for {target_os}...")
	dist_dir = f"dist/{PROJECT_FULL_NAME}"
	
	if target_os == "windows":
		rar_path = r"C:\Program Files\WinRAR\rar.exe"
		if not os.path.exists(rar_path):
			print("Error: WinRAR not found at %s" % rar_path)
			return
		f = File(password="", encode=False, aes=False)
		cmd_bat = "\"%s\" a -cfg- -ed -ep1 -k -m5 -r -sfx \"-ztools\\rar_options.txt\" \"%s.exe\" \"%s\\*\"" % (rar_path, PROJECT_FULL_NAME, dist_dir)
		f.save(cmd_bat, "_build.bat", mode="w+", type="txt")
		common.run("cmd /c _build.bat")
		if os.path.exists("_build.bat"):
			os.remove("_build.bat")
	else:
		shutil.make_archive(PROJECT_FULL_NAME, 'zip', dist_dir)
		print(f"Created archive: {PROJECT_FULL_NAME}.zip")


def quote_arg(path_str):
	path_str = str(path_str).strip()
	if " " in path_str and not (path_str.startswith('"') and path_str.endswith('"')):
		return f'"{path_str}"'
	return path_str


def find_local_gcc_or_clang(is_cpp=False):
	exe_gcc = "g++.exe" if is_cpp else "gcc.exe"
	exe_clang = "clang++.exe" if is_cpp else "clang.exe"

	if shutil.which(exe_gcc[:-4]):
		return exe_gcc[:-4]
	if shutil.which(exe_clang[:-4]):
		return exe_clang[:-4]

	search_patterns = [
		rf"C:\MinGW\bin\{exe_gcc}",
		rf"C:\MinGW64\bin\{exe_gcc}",
		rf"C:\mingw64\bin\{exe_gcc}",
		rf"C:\mingw32\bin\{exe_gcc}",
		rf"C:\TDM-GCC-64\bin\{exe_gcc}",
		rf"C:\TDM-GCC-32\bin\{exe_gcc}",
		rf"C:\msys64\mingw64\bin\{exe_gcc}",
		rf"C:\msys64\ucrt64\bin\{exe_gcc}",
		rf"C:\msys64\mingw32\bin\{exe_gcc}",
		rf"C:\msys64\usr\bin\{exe_gcc}",
		rf"C:\cygwin64\bin\{exe_gcc}",
		rf"C:\w64devkit\bin\{exe_gcc}",
		rf"C:\Program Files\mingw-w64\*\mingw64\bin\{exe_gcc}",
		rf"C:\Program Files (x86)\mingw-w64\*\mingw32\bin\{exe_gcc}",
		rf"C:\Program Files\LLVM\bin\{exe_clang}",
		rf"C:\Program Files (x86)\LLVM\bin\{exe_clang}",
		rf"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\Llvm\x64\bin\{exe_clang}",
		rf"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\Llvm\bin\{exe_clang}",
		rf"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\Llvm\x64\bin\{exe_clang}",
		rf"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\Llvm\bin\{exe_clang}",
		rf"C:\Program Files (x86)\CodeBlocks\MinGW\bin\{exe_gcc}",
		rf"C:\Program Files\CodeBlocks\MinGW\bin\{exe_gcc}",
		rf"C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\{exe_gcc}",
		rf"C:\Program Files\Dev-Cpp\MinGW64\bin\{exe_gcc}"
	]
	for pattern in search_patterns:
		matches = glob.glob(pattern)
		if matches:
			return quote_arg(matches[0])
	return None


def find_vs_vcvars(arch=None):
	arch_str = str(arch).lower() if arch else "x64"
	bat_name = "vcvars32.bat" if arch_str == "x86" else "vcvars64.bat"
	
	vs_roots = [
		os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
		os.environ.get("ProgramFiles", r"C:\Program Files")
	]
	
	for root in vs_roots:
		vswhere = os.path.join(root, "Microsoft Visual Studio", "Installer", "vswhere.exe")
		if os.path.exists(vswhere):
			for year in ["2022", "2019", "2017", "*"]:
				for ed in ["BuildTools", "Community", "Professional", "Enterprise", "*"]:
					pattern = os.path.join(root, "Microsoft Visual Studio", year, ed, "VC", "Auxiliary", "Build", bat_name)
					matches = glob.glob(pattern)
					if matches:
						return matches[0]

	for root in vs_roots:
		if not root or not os.path.exists(root):
			continue
		patterns = [
			os.path.join(root, "Microsoft Visual Studio", "*", "*", "VC", "Auxiliary", "Build", bat_name),
			os.path.join(root, "Microsoft Visual Studio", "*", "VC", "Auxiliary", "Build", bat_name),
			os.path.join(root, "Microsoft Visual Studio *", "VC", "bin", "amd64" if bat_name == "vcvars64.bat" else "", bat_name)
		]
		for p in patterns:
			matches = glob.glob(p)
			if matches:
				return matches[0]
	return None


def resolve_gcc_binary(host_os, target_os, arch=None, is_cpp=False):
	base_compiler = "g++" if is_cpp else "gcc"
	clang_compiler = "clang++" if is_cpp else "clang"
	arch_str = str(arch).lower() if arch else "x64"

	if host_os != target_os:
		candidates = []
		if target_os == "linux":
			if arch_str in ("arm64", "aarch64", "a64"):
				candidates = [f"aarch64-linux-gnu-{base_compiler}", f"aarch64-linux-musl-{base_compiler}"]
			elif arch_str in ("arm", "armhf", "armeabi-v7a"):
				candidates = [f"arm-linux-gnueabihf-{base_compiler}"]
			elif arch_str == "x86":
				candidates = [f"i686-linux-gnu-{base_compiler}"]
			else:
				candidates = [f"x86_64-linux-gnu-{base_compiler}", f"x86_64-linux-musl-{base_compiler}"]
		elif target_os == "macos":
			if arch_str in ("arm64", "aarch64", "m1", "m2"):
				candidates = [f"oa64-{clang_compiler}", f"arm64-apple-darwin-{base_compiler}"]
			else:
				candidates = [f"o64-{clang_compiler}", f"x86_64-apple-darwin-{base_compiler}"]
		elif target_os == "windows":
			candidates = [f"i686-w64-mingw32-{base_compiler}" if arch_str == "x86" else f"x86_64-w64-mingw32-{base_compiler}"]
		elif target_os == "android":
			candidates = [
				f"aarch64-linux-android21-{clang_compiler}" if arch_str in ("arm64-v8a", "a64", "aarch64") else f"armv7a-linux-androideabi21-{clang_compiler}",
				f"x86_64-linux-android21-{clang_compiler}" if arch_str == "x64" else f"i686-linux-android21-{clang_compiler}"
			]
		for cand in candidates:
			if shutil.which(cand.split()[0]):
				return ("gcc", cand)

	if host_os == "windows":
		found_gcc = find_local_gcc_or_clang(is_cpp)
		if found_gcc:
			return ("gcc", found_gcc)
		vcvars = find_vs_vcvars(arch)
		if vcvars:
			print(f"-> Found Visual Studio Build Tools: {vcvars}")
			return ("msvc", vcvars)

	return ("gcc", base_compiler)


def build_command(tool, PROJECT, PROJECT_FULL_NAME, rename_file, args_compile, zstandard, target_os, arch=None):
	tool = tool.lower().strip()
	host_os = sys_checker.get_platform()["os"].lower()
	if target_os == "android":
		raise ValueError("Android builds must use the dedicated BeeWare backend")
	args = list(args_compile) if isinstance(args_compile, list) else []
	out_dir = f"dist/{PROJECT_FULL_NAME}"
	ext_bin = ".exe" if target_os == "windows" else ""
	py_exe = _find_real_python()

	if host_os != target_os and tool in ("pyinstaller", "cx_freeze"):
		print(f"Notice: '{tool}' cannot cross-compile from '{host_os}' to '{target_os}'.")
		print(f"-> Automatically switching build tool to C/C++ compiler (GCC / VS Build Tools) for target '{target_os}'.")
		tool = "gcc"
		pyinst_flags = ("--noconsole", "-w", "--onefile", "-F", "--onedir", "-D", "--console", "-c", "--clean")
		args = [a for a in args if a.strip() not in pyinst_flags and not a.strip().startswith(("--add-data", "--hidden-import", "--icon", "-i"))]

	if tool == "pyinstaller":
		if zstandard:
			if not any(a.strip().startswith(("--onefile", "-F", "--onedir", "-D")) for a in args):
				args.append("--onefile")
			args = [a for a in args if not a.strip().startswith(("--name", "--distpath"))]
			args.append(f"--name {rename_file}")
			args.append(f"--distpath {out_dir}")
		return f"pyinstaller {' '.join(args)} {PROJECT}.py"

	elif tool == "nuitka":
		if zstandard:
			if not any(a.strip().startswith(("--onefile", "--standalone")) for a in args):
				args.append("--onefile")
			args = [a for a in args if not a.strip().startswith(("--output-dir", "--output-filename", "-o"))]
			args.append(f"--output-dir={out_dir}")
			args.append(f"--output-filename={rename_file}{ext_bin}")
		return f"{quote_arg(py_exe)} -m nuitka {' '.join(args)} {PROJECT}.py"

	elif tool in ("gcc", "g++", "clang", "msvc", "cl", "cython"):
		os.makedirs(out_dir, exist_ok=True)
		is_cpp = (tool == "g++") or os.path.exists(f"{PROJECT}.cpp")
		
		if tool in ("msvc", "cl"):
			vcvars = find_vs_vcvars(arch)
			comp_type, compiler = ("msvc", vcvars) if vcvars else ("msvc", "cl")
		elif tool == "clang" and shutil.which("clang"):
			comp_type, compiler = ("gcc", "clang")
		else:
			comp_type, compiler = resolve_gcc_binary(host_os, target_os, arch, is_cpp)

		out_file = os.path.normpath(f"{out_dir}/{rename_file}{ext_bin}")

		need_cython = False
		if tool != "cython" and os.path.exists(f"{PROJECT}.c"):
			src_file = f"{PROJECT}.c"
		elif tool != "cython" and os.path.exists(f"{PROJECT}.cpp"):
			src_file = f"{PROJECT}.cpp"
		else:
			need_cython = True
			src_file = f"{PROJECT}.c"

		cmds = []
		if need_cython:
			py_file = f"{PROJECT}.py"
			cython_bin = "cython" if shutil.which("cython") else f"{quote_arg(py_exe)} -m cython"
			cmds.append(f"{cython_bin} --embed -o {quote_arg(src_file)} {quote_arg(py_file)}")

		if comp_type == "msvc":
			inc_dir = sysconfig.get_path("include")
			libs_dir = os.path.join(sys.base_prefix, "libs")
			py_ver_num = f"{sys.version_info.major}{sys.version_info.minor}"
			
			msvc_flags = []
			if inc_dir and os.path.exists(inc_dir):
				msvc_flags.append(f'/I"{inc_dir}"')
			if libs_dir and os.path.exists(libs_dir):
				msvc_flags.append(f'/link /LIBPATH:"{libs_dir}" python{py_ver_num}.lib')

			py_flags = " ".join(msvc_flags) if need_cython else ""
			extra_args = " ".join(args)
			
			if compiler != "cl" and os.path.exists(compiler):
				bat_content = f'@echo off\ncall "{compiler}"\ncl /nologo /O2 {extra_args} {quote_arg(src_file)} {py_flags} /Fe:{quote_arg(out_file)}\n'
				f = File(password="", encode=False, aes=False)
				f.save(bat_content, "_vs_build.bat", mode="w+", type="txt")
				cmds.append("cmd /c _vs_build.bat")
			else:
				cmds.append(f"cl /nologo /O2 {extra_args} {quote_arg(src_file)} {py_flags} /Fe:{quote_arg(out_file)}")
		else:
			arch_flag = ""
			if arch and str(arch).lower() == "x86" and "-m32" not in compiler and "-m32" not in args:
				arch_flag = "-m32"
			elif arch and str(arch).lower() == "x64" and "-m64" not in compiler and "-m64" not in args and "arm" not in compiler and "aarch64" not in compiler:
				arch_flag = "-m64"
			extra_args = " ".join(filter(None, [arch_flag] + args))
			
			inc_dir = sysconfig.get_path("include")
			libs_dir = os.path.join(sys.base_prefix, "libs")
			py_ver_num = f"{sys.version_info.major}{sys.version_info.minor}"
			gcc_flags = []
			if inc_dir and os.path.exists(inc_dir):
				gcc_flags.append(f'-I"{inc_dir}"')
			if os.path.exists(libs_dir):
				gcc_flags.append(f'-L"{libs_dir}"')
			gcc_flags.append(f'-lpython{py_ver_num}')
			py_flags = " ".join(gcc_flags) if need_cython else ""
			
			win_def = "-DMS_WIN64" if (host_os == "windows" and need_cython) else ""
			cmds.append(f"{compiler} {extra_args} {quote_arg(src_file)} {py_flags} {win_def} -o {quote_arg(out_file)}".strip())

		return cmds

	elif tool == "cx_freeze":
		return f"cxfreeze {PROJECT}.py --target-dir {out_dir} --target-name {rename_file}{ext_bin} {' '.join(args)}"

	elif tool in ("beeware", "briefcase"):
		return f"{quote_arg(py_exe)} -I -m briefcase package android --packaging-format apk --adhoc-sign --no-input"

	else:
		return f"{tool} {' '.join(args)} {PROJECT}.py"


def run_build_step(cmd_or_list, project_name):
	cmds = cmd_or_list if isinstance(cmd_or_list, list) else [c.strip() for c in cmd_or_list.split("&&") if c.strip()]
	for idx, single_cmd in enumerate(cmds):
		subprocess.run(single_cmd, shell=True, check=True)
		if idx == 0 and len(cmds) > 1 and "--embed" in single_cmd:
			c_file = f"{project_name}.c"
			if not os.path.exists(c_file):
				print(f"Error: Cython failed to generate '{c_file}'. Stopping compile step.")
				return False
	if os.path.exists("_vs_build.bat"):
		try:
			os.remove("_vs_build.bat")
		except Exception:
			pass
	if os.path.exists(f"{project_name}.obj"):
		try:
			os.remove(f"{project_name}.obj")
		except Exception:
			pass
	return True


def build(PROJECT=None, PROJECT_FULL_NAME=None, args_compile=[], data=[], rename_file=None, packet=False, zstandard=True, mode="pyinstaller", platforms=None, arch=None):
	if PROJECT is None and PROJECT_FULL_NAME is None:
		print("Error: you should fill full project or file name you want compile!")
		sys.exit(1)
	if PROJECT is None:
		PROJECT = PROJECT_FULL_NAME
	elif PROJECT_FULL_NAME is None:
		PROJECT_FULL_NAME = PROJECT

	if not isinstance(args_compile, list):
		args_compile = [str(args_compile)] if args_compile else []
	if not isinstance(data, list):
		data = [str(data)] if data else []
	if rename_file is None:
		rename_file = PROJECT_FULL_NAME

	if not platforms:
		target_platforms = [sys_checker.get_platform()["os"]]
	elif isinstance(platforms, str):
		target_platforms = [platforms.lower().strip()]
	elif isinstance(platforms, list):
		target_platforms = [p.lower().strip() for p in platforms]
	else:
		target_platforms = [sys_checker.get_platform()["os"]]

	for target_os in target_platforms:
		if len(target_platforms) > 1:
			current_full_name = f"{PROJECT_FULL_NAME}_{target_os}"
		else:
			current_full_name = PROJECT_FULL_NAME

		copydir = f"dist/{current_full_name}"

		if target_os == "android":
			valid_android_modes = ("beeware", "briefcase", "android", "buildozer")
			if mode.lower().strip() not in valid_android_modes:
				print(f"Notice: Mode '{mode}' is for desktop. Automatically switching to 'beeware' for Android APK build.")

			build_android(
				project=PROJECT,
				name=PROJECT_FULL_NAME,
				data=data,
				arch=arch,
				args=args_compile,
				prepare_only="--skip-compile" in sys.argv,
				rename_file=rename_file,
				out_dir=copydir
			)
			if packet:
				dopackage(PROJECT, current_full_name, target_os)
			continue

		print("=" * 50)
		print(f"Building '{PROJECT}' -> '{PROJECT_FULL_NAME}' | Tool: {mode} | Target OS: {target_os} | Arch: {arch or 'auto'}")

		if "--skip-compile" in sys.argv:
			print("Skipping compile step...")
		else:
			cmd = build_command(mode, PROJECT, current_full_name, rename_file, args_compile, zstandard, target_os, arch)
			if not run_build_step(cmd, PROJECT):
				raise RuntimeError("Build failed; packaging stopped")

		print(f"Making libraries for {target_os}...")
		try:
			copy_platform_libs("pyaudiogaming", copydir, target_os, arch)
			if data:
				for elem in data:
					if os.path.exists(elem):
						print(f"Copying data: {elem}...")
						dest_elem = os.path.join(copydir, elem)
						if os.path.isdir(elem):
							shutil.copytree(elem, dest_elem, dirs_exist_ok=True)
						else:
							os.makedirs(os.path.dirname(dest_elem), exist_ok=True)
							shutil.copy2(elem, dest_elem)
		except Exception as e:
			print(f"Warning while copying libraries/data: {e}")

		if packet:
			dopackage(PROJECT, current_full_name, target_os)

	print("Done!")


def create_template(filename="build.txt", legacy=False):
	f = File(password="", encode=False, aes=False)
	if not legacy:
		content = (
			"# PyAudioGaming Build Configuration (Key-Value Format)\n"
			"# Lines starting with #, //, !, @ will be ignored\n\n"
			"project = main\n"
			"project_full_name = MyAudioGame\n"
			"args_compile = [--noconsole]\n"
			"data = [sounds, data]\n"
			"rename_file = game\n"
			"packet = false\n"
			"zstandard = true\n"
			"mode = pyinstaller\n"
			"platforms = null\n"
			"arch = null\n"
		)
	else:
		content = (
			"# PyAudioGaming Build Configuration (Legacy Line-by-Line Format)\n"
			"# Line order: PROJECT, PROJECT_FULL_NAME, args_compile, data, rename_file, packet, zstandard, mode, platforms, arch\n\n"
			"main\n"
			"MyAudioGame\n"
			"[--noconsole]\n"
			"[sounds, data]\n"
			"game\n"
			"false\n"
			"true\n"
			"pyinstaller\n"
			"null\n"
			"null\n"
		)
	f.save(content, filename, mode="w+", type="txt")
	fmt_name = "legacy (line-by-line)" if legacy else "new (key = value)"
	print(f"Created {fmt_name} template configuration file: {filename}")


def interactive_make():
	print("=== Interactive Configuration & Build Wizard (MAKE) ===")
	print("Instructions: Type '.' to go back 1 step, '..' to go back 2 steps. Press Enter to accept the default value.\n")

	steps = [
		("PROJECT", "Main script file name (without .py, e.g., main)", "main"),
		("PROJECT_FULL_NAME", "Full project / output directory name (Press Enter to use main file name)", ""),
		("args_compile", "Compiler arguments (e.g., [--noconsole] or leave empty)", "[]"),
		("data", "Additional data files/folders to copy (e.g., [sounds, data] or leave empty)", "[]"),
		("rename_file", "Executable output name after build (Press Enter to use project name)", ""),
		("packet", "Create installer / zip archive after build? (true/false)", "false"),
		("zstandard", "Use standard automated flags (zstandard)? (true/false)", "true"),
		("mode", "Compiler tool (pyinstaller, nuitka, cython, gcc, msvc, cx_freeze, beeware for Android)", "pyinstaller"),
		("platforms", "Target OS (windows, linux, android, macos, ios, or null for auto-detect)", "null"),
		("arch", "Target CPU architecture (x64, x86, a64, arm64-v8a... or null for auto-detect)", "null"),
		("save_action", "Save config or build immediately? (Enter .txt filename to save only, 'both' to save & build, or press Enter to build now)", "")
	]

	answers = {}
	idx = 0
	total = len(steps)

	while idx < total:
		key, prompt_text, default_val = steps[idx]
		cur_val = answers.get(key, default_val)
		display_default = f" [{cur_val}]" if cur_val != "" else ""
		
		try:
			user_inp = input(f"({idx + 1}/{total}) {prompt_text}{display_default}: ").strip()
		except (KeyboardInterrupt, EOFError):
			print("\nMake operation cancelled.")
			sys.exit(0)

		if user_inp and all(c == "." for c in user_inp):
			back_steps = len(user_inp)
			idx = max(0, idx - back_steps)
			print(f"--> Stepped back to ({idx + 1}/{total}): {steps[idx][0]}")
			continue

		if user_inp == "":
			answers[key] = cur_val
		else:
			answers[key] = user_inp

		idx += 1

	config = {
		"PROJECT": parse_val(answers["PROJECT"]),
		"PROJECT_FULL_NAME": parse_val(answers["PROJECT_FULL_NAME"]) or parse_val(answers["PROJECT"]),
		"args_compile": parse_val(answers["args_compile"]) or [],
		"data": parse_val(answers["data"]) or [],
		"rename_file": parse_val(answers["rename_file"]) or None,
		"packet": bool(parse_val(answers["packet"])),
		"zstandard": bool(parse_val(answers["zstandard"])),
		"mode": parse_val(answers["mode"]) or "pyinstaller",
		"platforms": parse_val(answers["platforms"]),
		"arch": parse_val(answers["arch"])
	}

	save_act = answers["save_action"].strip()
	if save_act:
		f = File(password="", encode=False, aes=False)
		do_build_too = False
		if save_act.lower() == "both":
			out_txt = "build.txt"
			do_build_too = True
		else:
			out_txt = save_act if "." in save_act else f"{save_act}.txt"

		lines = [
			"# Generated by PyAudioGaming compile make",
			f"project = {config['PROJECT'] or 'null'}",
			f"project_full_name = {config['PROJECT_FULL_NAME'] or 'null'}",
			f"args_compile = [{', '.join(config['args_compile'])}]" if isinstance(config['args_compile'], list) else f"args_compile = [{config['args_compile']}]",
			f"data = [{', '.join(config['data'])}]" if isinstance(config['data'], list) else f"data = [{config['data']}]",
			f"rename_file = {config['rename_file'] or 'null'}",
			f"packet = {str(config['packet']).lower()}",
			f"zstandard = {str(config['zstandard']).lower()}",
			f"mode = {config['mode']}",
			f"platforms = {config['platforms'] or 'null'}",
			f"arch = {config['arch'] or 'null'}"
		]
		content = "\n".join(lines) + "\n"
		f.save(content, out_txt, mode="w+", type="txt")
		print(f"\nConfiguration saved to: {out_txt}")
		if not do_build_too:
			return

	print("\nStarting build process...")
	build(**config)


def work(config_file):
	# Nếu đang ở trong tiến trình con của Android build thì thoát êm ngay, không báo lỗi build.txt
	if os.environ.get("PYAG_BUILDING_ANDROID") == "1" or "briefcase" in " ".join(sys.argv).lower():
		return

	f = File(password="", encode=False, aes=False)
	if not f.check(config_file):
		# Nếu bị gọi nhầm từ thư mục workspace của Android thì bỏ qua, không sys.exit(1)
		cwd_lower = os.getcwd().lower()
		if "android" in cwd_lower or "projects" in cwd_lower:
			return
		print(f"Error: Config file '{config_file}' not found!")
		return

	text = f.load(config_file, mode="r+", type="txt")
	if not text:
		return

	lines = []
	for line in text.splitlines():
		s = line.strip()
		if not s or s.startswith(("#", "//", "!", "@")):
			continue
		lines.append(s)

	if not lines:
		print("Error: Empty configuration file!")
		return

	is_kv = any("=" in line and not line.startswith("[") for line in lines)

	if is_kv:
		config = {
			"PROJECT": None,
			"PROJECT_FULL_NAME": None,
			"args_compile": [],
			"data": [],
			"rename_file": None,
			"packet": False,
			"zstandard": True,
			"mode": "pyinstaller",
			"platforms": None,
			"arch": None
		}
		key_map = {
			"project": "PROJECT",
			"file": "PROJECT",
			"project_full_name": "PROJECT_FULL_NAME",
			"full_name": "PROJECT_FULL_NAME",
			"args_compile": "args_compile",
			"args": "args_compile",
			"data": "data",
			"rename_file": "rename_file",
			"rename": "rename_file",
			"packet": "packet",
			"zstandard": "zstandard",
			"mode": "mode",
			"tool": "mode",
			"tools": "mode",
			"platform": "platforms",
			"platforms": "platforms",
			"os": "platforms",
			"arch": "arch"
		}
		for line in lines:
			if "=" not in line:
				continue
			k, v = line.split("=", 1)
			if "#" in v and not ("'" in v or '"' in v):
				v = v.split("#", 1)[0]
			k = k.strip().lower()
			val = parse_val(v)
			if k in key_map:
				config[key_map[k]] = val
		build(**config)
	else:
		if len(lines) < 6:
			print("Error: not true type of compile building config pyaudiogaming needs!")
			return
		parsed_args = [parse_val(line) for line in lines]
		build(*parsed_args)


if __name__ == "__main__":
	if len(sys.argv) < 2:
		sys.exit(0)

	user_input = sys.argv[1].strip()

	# Chặn các lệnh của Briefcase nếu bị gọi nhầm vào compile.py
	briefcase_subcommands = {"new", "dev", "upgrade", "update", "open", "build", "run", "package", "publish", "log", "--version", "-V", "--help", "-h"}
	if user_input.lower() in briefcase_subcommands:
		sys.exit(0)
	if user_input.lower() == "create" and len(sys.argv) > 2 and sys.argv[2].lower() in ("android", "ios", "windows", "linux", "macos"):
		sys.exit(0)

	if user_input.lower() == "make":
		interactive_make()
	elif user_input.lower() == "create":
		target_file = sys.argv[2] if len(sys.argv) > 2 else "build.txt"
		if "." not in target_file:
			target_file += ".txt"
		create_template(target_file, legacy=False)
	elif user_input.lower() == "create2":
		target_file = sys.argv[2] if len(sys.argv) > 2 else "build.txt"
		if "." not in target_file:
			target_file += ".txt"
		create_template(target_file, legacy=True)
	else:
		config_file = user_input
		if not config_file.endswith(".txt") and os.path.exists(config_file + ".txt"):
			config_file += ".txt"
		
		config_file = os.path.abspath(config_file)
		if os.path.isfile(config_file):
			work(config_file)
		else:
			sys.exit(0)