#!/usr/bin/env python3
"""Run Selma source checks and optional Android build without GitHub Actions.

From a complete local checkout:
    python tools/ci_free_local.py
    python tools/ci_free_local.py --android
This program never submits a GitHub Actions job or changes billing settings.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {".git", ".venv", "venv", "node_modules", "build", "dist", ".gradle"}


def run(command, cwd=ROOT):
    cmd = [str(x) for x in command]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def validate_json():
    checked = 0
    for path in sorted(ROOT.rglob("*.json")):
        if EXCLUDE.intersection(path.relative_to(ROOT).parts):
            continue
        with path.open(encoding="utf-8") as stream:
            json.load(stream)
        checked += 1
    print(f"JSON validated: {checked} file(s)")


def validate_shell():
    bash = shutil.which("bash")
    if not bash:
        print("INCOMPLETE: Bash missing; shell checks and agent smoke test NOT_RUN.")
        print("Install Git Bash (Windows) or Bash, then rerun for full core verification.")
        return False
    scripts = sorted(
        p for p in ROOT.rglob("*.sh")
        if not EXCLUDE.intersection(p.relative_to(ROOT).parts)
    )
    for script in scripts:
        run([bash, "-n", script.relative_to(ROOT)])
    run([bash, "SELMA0_ANDROID_AGENT_V1/selma0_smoke_test_android_v1.sh"])
    print(f"Bash syntax validated: {len(scripts)} file(s)")
    return True


def build_android():
    project = ROOT / "SELMA0_ANDROID_NATIVE_V1"
    if not project.is_dir():
        raise RuntimeError("Native Android project is missing.")
    if not shutil.which("java"):
        raise RuntimeError("Java 17 is needed on PATH for Android Gradle build.")
    if not (os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")):
        raise RuntimeError("Set ANDROID_HOME or ANDROID_SDK_ROOT to an installed Android SDK.")
    tasks = [":app:lintDebug", ":app:testDebugUnitTest", ":app:assembleDebug"]
    if os.name == "nt":
        command = ["cmd", "/c", "gradlew.bat", "--no-daemon", *tasks]
    else:
        command = ["./gradlew", "--no-daemon", *tasks]
    run(command, cwd=project)
    apk = project / "app/build/outputs/apk/debug/app-debug.apk"
    if not apk.is_file():
        raise RuntimeError("Gradle returned without the expected debug APK.")
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    print(f"APK: {apk}\nSHA256: {digest}")
    print("APK assembled. Physical-device install, security review and offline behavior remain NOT_VERIFIED.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", action="store_true", help="Also build the debug Android APK (Java 17 and Android SDK required)")
    args = parser.parse_args()
    os.chdir(ROOT)
    if sys.version_info < (3, 12):
        parser.error("Python 3.12 or newer is required.")

    print("Selma local CI | independent of GitHub Actions | no hosted runner charges", flush=True)
    run([sys.executable, "-m", "compileall", "-q", "SELMA0_ANDROID_AGENT_V1", "adapters", "core", "tests", "tools"])
    run([sys.executable, "SELMA0_ANDROID_AGENT_V1/tests/test_procurement_gate_v1.py"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "SELMA0_ANDROID_AGENT_V1/tests", "-p", "test_*.py", "-v"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
    run([sys.executable, "tools/generate_support_matrix.py", "--check"])
    validate_json()
    bash_complete = validate_shell()
    if args.android:
        build_android()
    if not bash_complete:
        print("PARTIAL: Python/JSON checks executed; Bash checks NOT_RUN. This is not a full CI PASS.")
        return 2
    print("PASS: local checks executed successfully. GitHub Actions and Android device tests are NOT_VERIFIED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.CalledProcessError, OSError, ValueError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
