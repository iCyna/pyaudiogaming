# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 ihcyna (Labubu) <phucnggo29@gmail.com>. All rights reserved.
"""
Push a minimal 2-file staging branch ('g2rt-ios-build') to GitHub Actions
so macos-14 builds g2rt_ios_arm64.ipa and g2rt_ios_simulator.ipa cleanly
without touching 'main' or uploading any large game assets.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

G2RT_DIR = Path(__file__).resolve().parent
REPO_DIR = G2RT_DIR.parent.parent
REMOTE_URL = "git@github.com:iCyna/The-Thousand-Things.git"
TARGET_BRANCH = "g2rt-ios-build"
ACTIONS_URL = "https://github.com/iCyna/The-Thousand-Things/actions"


def main():
    stage_dir = Path(tempfile.mkdtemp(prefix="pyag_ios_push_"))
    try:
        wf_dst = stage_dir / ".github" / "workflows" / "build_ios_runtime.yml"
        wf_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_DIR / ".github" / "workflows" / "build_ios_runtime.yml", wf_dst)

        bs_dst = stage_dir / "pyaudiogaming" / "include" / "g2rt" / "bootstrap.py"
        bs_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(G2RT_DIR / "bootstrap.py", bs_dst)

        subprocess.run(["git", "init", "-q"], cwd=stage_dir, check=True)
        subprocess.run(["git", "checkout", "-b", TARGET_BRANCH, "-q"], cwd=stage_dir, check=True)
        subprocess.run(["git", "add", "-A"], cwd=stage_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Build G2RT iOS runtimes (arm64 & simulator)", "-q"], cwd=stage_dir, check=True)
        subprocess.run(["git", "remote", "add", "origin", REMOTE_URL], cwd=stage_dir, check=True)

        print(f"[G2RT:iOS] Pushing minimal 2-file branch '{TARGET_BRANCH}' to {REMOTE_URL} ...")
        res = subprocess.run(["git", "push", "--force", "origin", TARGET_BRANCH], cwd=stage_dir, capture_output=True, text=True)
        if res.returncode != 0:
            print("[ERROR] git push failed:\n", res.stderr)
            return res.returncode

        print(res.stdout or res.stderr)
        print(f"[OK] Pushed! GitHub Actions is now building g2rt_ios_arm64.ipa & g2rt_ios_simulator.ipa.")
        print(f"Open: {ACTIONS_URL}")
        return 0
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
