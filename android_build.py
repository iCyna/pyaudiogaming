# -*- coding: utf-8 -*-
"""Prepare and build a standalone Android APK using BeeWare (Briefcase) portably."""

from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import zipfile

try:
	from pyaudiogaming.file import File
except ImportError:
	sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
	from pyaudiogaming.file import File

ROOT = Path(__file__).resolve().parent
ABIS = {"arm64-v8a", "armeabi-v7a", "x86", "x86_64"}

# Thư mục chứa Toolchain di động (SDK, NDK, JDK, Gradle dùng chung cho mọi dự án)
PORTABLE_HOME = ROOT / "include" / "android" / "toolchain"

EXCLUDE_BUILD_FILES = {
	"compile.py", "compile_2.py", "builder.py", "android_build.py", "setup.py",
	"buildapp.py", "buildtranslation.py", "@build.py"
}

EXCLUDE_DIRS = {
	"__pycache__", "android", "build", "dist", "venv", ".venv", "env", ".git", ".idea", ".vscode", "logs"
}

DESKTOP_BIN_PATTERNS = (
	"*.dll", "*.exe", "*.pyd", "*.dylib", "*.chm", "*.pdb", "*.lib", "*.exp", "*.obj", "*.a", "*.bat", "*.cmd"
)


def _save_text(content, path):
	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(str(content), encoding="utf-8")


def _load_text(path):
	return Path(path).read_text(encoding="utf-8")


def _find_real_python():
	"""Tìm python.exe thật để tránh trường hợp sys.executable đang trỏ vào file .exe đã đóng gói."""
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

	tools_dir = PORTABLE_HOME / "tools"
	if tools_dir.is_dir():
		for jdk_cand in sorted(tools_dir.glob("java*"), reverse=True):
			if (jdk_cand / "bin").is_dir():
				env["JAVA_HOME"] = str(jdk_cand)
				env["PATH"] = str(jdk_cand / "bin") + os.pathsep + env.get("PATH", "")
				break
		sdk_cand = tools_dir / "android_sdk"
		if sdk_cand.is_dir():
			env["ANDROID_HOME"] = str(sdk_cand)
			env["ANDROID_SDK_ROOT"] = str(sdk_cand)

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
	cmd = [py_exe, "-I", "-m", "briefcase"] + list(args_list)
	res = subprocess.run(cmd, cwd=cwd, env=env)
	if res.returncode != 0:
		raise RuntimeError(
			f"Briefcase failed at command: briefcase {' '.join(args_list)} (exit code {res.returncode})"
		)


def _normalize_abis(arch=None):
	raw = arch if isinstance(arch, list) else [arch or "arm64-v8a"]
	# Lưu ý: nhiều người dùng để arch="x64" từ cấu hình Windows, trên đt Android cần ưu tiên arm64-v8a
	aliases = {
		"a64": "arm64-v8a",
		"arm64": "arm64-v8a",
		"aarch64": "arm64-v8a",
		"x64": "arm64-v8a",
		"arm": "armeabi-v7a",
		"armv7": "armeabi-v7a",
		"a86": "x86"
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
	if sys.version_info >= (3, 12):
		supported_64 = [a for a in abis if a in ("arm64-v8a", "x86_64")]
		if supported_64 != abis:
			print(
				f"[BeeWare] Notice: Python {sys.version_info.major}.{sys.version_info.minor} on Android "
				f"only supports 64-bit ABIs. Adjusting ABIs {abis} -> {supported_64 or ['arm64-v8a']}"
			)
			abis = supported_64 or ["arm64-v8a"]
	return abis


def _collect_and_verify_libs(abis, app_root, staging_native_dir, package_lib_dir):
	if staging_native_dir.exists():
		shutil.rmtree(staging_native_dir)
	staging_native_dir.mkdir(parents=True, exist_ok=True)
	if package_lib_dir.exists():
		shutil.rmtree(package_lib_dir)

	for abi in abis:
		src_dirs = [
			ROOT / "lib" / abi,
			app_root / "lib" / abi,
			app_root / "pyaudiogaming" / "lib" / abi
		]
		target_jni = staging_native_dir / abi
		target_jni.mkdir(parents=True, exist_ok=True)

		copied_files = set()
		for sdir in src_dirs:
			if not sdir.is_dir():
				continue
			for so_file in sdir.glob("*.so"):
				fname = so_file.name
				lib_fname = fname if fname.startswith("lib") else f"lib{fname}"
				shutil.copy2(so_file, target_jni / lib_fname)
				copied_files.add(lib_fname)

		for required in ("libbass.so", "libbassmix.so", "libbass_fx.so"):
			if required not in copied_files:
				raise ValueError(
					f"Missing required Android library '{required}' for ABI '{abi}'. "
					f"Expected inside: {ROOT / 'lib' / abi}"
				)


def _patch_android_manifest(manifest_path):
	if not manifest_path.exists():
		return
	text = _load_text(manifest_path)
	# Sửa các quyền bị thiếu tiền tố android.permission.
	for short_perm in ("INTERNET", "ACCESS_NETWORK_STATE", "RECORD_AUDIO", "MODIFY_AUDIO_SETTINGS", "WAKE_LOCK"):
		bad_tag = f'<uses-permission android:name="{short_perm}"/>'
		good_tag = f'<uses-permission android:name="android.permission.{short_perm}"/>'
		if bad_tag in text:
			if good_tag in text:
				text = text.replace(bad_tag, "")
			else:
				text = text.replace(bad_tag, good_tag)
	if 'android:extractNativeLibs=' not in text and '<application' in text:
		text = text.replace('<application', '<application\n        android:extractNativeLibs="true"', 1)
	_save_text(text, manifest_path)


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

	_patch_android_manifest(gradle_app_dir / "src" / "main" / "AndroidManifest.xml")

	build_gradle_path = gradle_app_dir / "build.gradle"
	if build_gradle_path.exists():
		gradle_text = _load_text(build_gradle_path)
		marker = "// [PYAUDIOGAMING_JNILIBS_PATCH]"
		if marker in gradle_text:
			gradle_text = gradle_text.split(marker)[0].rstrip()

		abi_filters = ", ".join(f'"{a}"' for a in abis)
		patch_block = f"""
{marker}
android {{
    defaultConfig {{
        targetSdkVersion 34
        ndk {{
            abiFilters.clear()
            abiFilters {abi_filters}
        }}
        python {{
            extractPackages "*"
        }}
    }}
    buildTypes {{
        release {{
            signingConfig signingConfigs.debug
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


def _is_apk_signed(apk_path):
	apk_path = Path(apk_path)
	if not apk_path.is_file() or apk_path.name.lower().endswith("-unsigned.apk"):
		return False
	try:
		with zipfile.ZipFile(apk_path, "r") as zf:
			names = zf.namelist()
			if any(
				n.startswith("META-INF/") and n.upper().endswith((".RSA", ".DSA", ".EC"))
				for n in names
			):
				return True
		with apk_path.open("rb") as f:
			size = apk_path.stat().st_size
			read_len = min(size, 65536 + 1024)
			f.seek(max(0, size - read_len))
			tail = f.read()
			if b"APK Sig Block 42" in tail:
				return True
	except Exception:
		return False
	return False


def _ensure_apk_signed(apk_path, env):
	apk_path = Path(apk_path)
	if _is_apk_signed(apk_path):
		return apk_path

	print(f"[BeeWare] APK '{apk_path.name}' is unsigned. Signing with Android debug keystore...")
	sdk_dir = PORTABLE_HOME / "tools" / "android_sdk"
	signers = sorted(sdk_dir.glob("build-tools/*/apksigner.bat"), reverse=True) if sdk_dir.exists() else []
	if not signers:
		raise RuntimeError(f"APK '{apk_path}' is unsigned and apksigner was not found in {sdk_dir}")

	keystore = Path.home() / ".android" / "debug.keystore"
	if not keystore.exists():
		keystore = PORTABLE_HOME / "debug.keystore"
	if not keystore.exists():
		keystore.parent.mkdir(parents=True, exist_ok=True)
		keytool_cands = sorted((PORTABLE_HOME / "tools").glob("java*/bin/keytool.exe"), reverse=True)
		keytool = str(keytool_cands[0]) if keytool_cands else "keytool"
		subprocess.run(
			[
				keytool, "-genkeypair", "-v",
				"-keystore", str(keystore),
				"-storepass", "android",
				"-alias", "androiddebugkey",
				"-keypass", "android",
				"-keyalg", "RSA",
				"-keysize", "2048",
				"-validity", "10000",
				"-dname", "CN=Android Debug,O=Android,C=US"
			],
			env=env,
			check=True
		)

	subprocess.run(
		[
			str(signers[0]), "sign",
			"--ks", str(keystore),
			"--ks-pass", "pass:android",
			"--ks-key-alias", "androiddebugkey",
			"--key-pass", "pass:android",
			str(apk_path)
		],
		env=env,
		check=True
	)
	return apk_path


def _is_ignored_app_dir(item_path, root_path):
	if item_path.resolve() == root_path.resolve():
		return True
	name_low = item_path.name.lower()
	if name_low in EXCLUDE_DIRS or name_low in ("pyaudiogaming", "server", "lib", "include", "scripts"):
		return True
	if name_low.startswith((".", "#", "@", "venv")):
		return True
	if (item_path / "pyvenv.cfg").exists() or (item_path / "Lib" / "site-packages").exists():
		return True
	return False


def prepare(project, name, data=(), arch=None, extra_reqs=()):
	entry = Path(str(project) + ".py").resolve()
	if not entry.is_file():
		raise ValueError(f"Entry script does not exist: {entry}")

	abis = _normalize_abis(arch)
	slug = re.sub(r"[^a-z0-9_]", "", str(name).lower().replace(" ", "_"))
	slug = re.sub(r"_+", "_", slug).strip("_")
	if not slug or not slug[0].isalpha():
		slug = "app_" + slug
	if slug in ("main", "test", "app", "sys", "os", "pyaudiogaming"):
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
			ignore_fn = shutil.ignore_patterns(
				"__pycache__", "*.pyc", "desktop.ini", "android",
				"compile*.py", "android_build.py", "builder.py",
				*DESKTOP_BIN_PATTERNS
			)
			shutil.copytree(src_folder, package / folder, dirs_exist_ok=True, ignore=ignore_fn)

	app_root = entry.parent
	for item in app_root.iterdir():
		if item.is_file() and item.suffix == ".py":
			fname_low = item.name.lower()
			if (
				fname_low not in EXCLUDE_BUILD_FILES
				and not fname_low.startswith(("compile", "#", "@"))
			):
				shutil.copy2(item, app_src / item.name)
		elif item.is_dir() and (item / "__init__.py").exists() and not _is_ignored_app_dir(item, ROOT):
			shutil.copytree(
				item,
				app_src / item.name,
				dirs_exist_ok=True,
				ignore=shutil.ignore_patterns(
					"__pycache__", "*.pyc", "desktop.ini",
					"compile*.py", "android_build.py", "builder.py",
					"Lib", "Scripts", "Include",
					*DESKTOP_BIN_PATTERNS
				)
			)

	shutil.copy2(entry, app_src / "main.py")
	shutil.copy2(entry, app_src / "_pyag_entry.py")

	_save_text("# Auto-generated package init\n", app_src / "__init__.py")
	bootstrap_code = """# -*- coding: utf-8 -*-
import os
import runpy
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

_ns = runpy.run_module("_pyag_entry", run_name="__main__", alter_sys=True)
"""
	_save_text(bootstrap_code, app_src / "__main__.py")

	for value in (data or ()):
		relative = Path(value)
		if relative.is_absolute() or ".." in relative.parts:
			raise ValueError(f"Data must be a relative path inside the application: {value}")
		if relative.suffix.lower() in (".dll", ".exe", ".pyd", ".dylib", ".lib", ".pdb"):
			print(f"[BeeWare] Skipping desktop binary in Android data: {value}")
			continue
		original = app_root / relative
		if not original.exists():
			original = Path(value).resolve()
		if not original.exists():
			raise ValueError(f"Missing application data: {original}")
		destination = app_src / relative
		if original.is_dir():
			data_ignore = shutil.ignore_patterns(
				"__pycache__", "*.pyc", "desktop.ini",
				"x64", "x86", "mac", "ios", "iosimulator", "armhf", "aarch64", "a86",
				*DESKTOP_BIN_PATTERNS
			)
			shutil.copytree(original, destination, dirs_exist_ok=True, ignore=data_ignore)
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
	abis_formatted = ", ".join(f'"{a}"' for a in abis)
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
android_abis = [{abis_formatted}]
build_gradle_dependencies = [
    "androidx.appcompat:appcompat:1.0.2",
    "androidx.constraintlayout:constraintlayout:1.1.3",
    "androidx.swiperefreshlayout:swiperefreshlayout:1.1.0",
]

[tool.briefcase.app.{slug}.android.permission]
"android.permission.INTERNET" = true
"android.permission.ACCESS_NETWORK_STATE" = true
"android.permission.RECORD_AUDIO" = true
"android.permission.MODIFY_AUDIO_SETTINGS" = true
"android.permission.WAKE_LOCK" = true
"""
	_save_text(pyproject_content, workspace / "pyproject.toml")
	return workspace, slug, abis, staging_native_dir, app_root


def build_android(project, name, data=(), arch=None, args=(), prepare_only=False, rename_file=None, out_dir=None):
	extra_reqs = [a for a in (args or ()) if not str(a).startswith("-")]
	clean_rebuild = "--clean" in (args or ()) or "--clean" in sys.argv

	workspace, slug, abis, staging_native_dir, app_root = prepare(
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

	# Xóa các file APK cũ (đặc biệt là APK unsigned từ lần build trước) trong workspace/dist
	if (workspace / "dist").exists():
		shutil.rmtree(workspace / "dist")

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

	print("[BeeWare] Step 4/4: Packaging signed standalone APK...")
	_run_briefcase(
		["package", "android", "--packaging-format", "debug-apk", "--no-input"],
		cwd=workspace, env=env
	)

	found_apks = []
	for search_root in (workspace / "dist", gradle_project_dir / "app" / "build" / "outputs" / "apk"):
		if search_root.exists():
			for p in search_root.rglob("*.apk"):
				if not p.name.lower().endswith("-unsigned.apk"):
					found_apks.append(p)

	if not found_apks:
		raise RuntimeError("Briefcase finished but no signed .apk file was found in outputs!")

	found_apks.sort(key=lambda p: (_is_apk_signed(p), p.stat().st_mtime), reverse=True)
	best_apk = _ensure_apk_signed(found_apks[0], env)

	target_dist = Path(out_dir) if out_dir else (app_root / "dist" / str(name))
	target_dist.mkdir(parents=True, exist_ok=True)

	apk_base = rename_file if rename_file else slug
	if not str(apk_base).lower().endswith(".apk"):
		apk_base = f"{apk_base}.apk"

	final_apk_path = target_dist / apk_base
	shutil.copy2(best_apk, final_apk_path)

	print("=" * 60)
	print(f"[BeeWare] Standalone signed APK successfully generated:")
	print(f" -> {final_apk_path.resolve()}")
	print("=" * 60)
	return True
