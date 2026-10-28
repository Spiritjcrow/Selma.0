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
import signal
import socket
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {".git", ".venv", "venv", "node_modules", "build", "dist", ".gradle"}
CORE_TIMEOUT_SECONDS = 300
SMOKE_TIMEOUT_SECONDS = 240
ANDROID_TIMEOUT_SECONDS = 1800


def terminate_group(process):
    """Best-effort teardown of only this runner's dedicated process group."""
    if os.name == "nt":
        # Windows taskkill cannot always find descendants once a parent exited.
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            time.sleep(0.2)
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait()


def run(command, cwd=None, *, timeout=CORE_TIMEOUT_SECONDS, env=None,
        cleanup_on_failure=False):
    """Bound subprocesses, with opt-in descendant cleanup for smoke launchers."""
    if cwd is None:
        cwd = ROOT
    cmd = [str(x) for x in command]
    print("+", " ".join(cmd), flush=True)
    opts = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt" else {"start_new_session": True}
    )
    with subprocess.Popen(cmd, cwd=cwd, env=env, **opts) as process:
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_group(process)
            raise
        if returncode:
            if cleanup_on_failure:
                terminate_group(process)
            raise subprocess.CalledProcessError(returncode, cmd)


def git_stdout(*args):
    """Read bounded local Git metadata, never treating a nested parent repo as ours."""
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True,
        text=True, timeout=20,
    ).stdout.strip()


def revision(expected_sha=None):
    """Require a clean, source-bound checkout; do not claim remote authenticity.

    A locally matching SHA is not proof of GitHub identity or signature trust.
    An owner may supply an independently obtained exact PR commit as expected_sha.
    """
    if not shutil.which("git"):
        raise RuntimeError("Git is required to identify the tested source revision.")
    top = Path(git_stdout("rev-parse", "--show-toplevel")).resolve()
    if os.path.normcase(str(top)) != os.path.normcase(str(ROOT.resolve())):
        raise RuntimeError("Not executing from the root of the intended Git checkout.")
    head = git_stdout("rev-parse", "--verify", "HEAD^{commit}").lower()
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise RuntimeError("Unable to determine exact Git commit.")
    if expected_sha is not None:
        if len(expected_sha) != 40 or any(ch not in "0123456789abcdef" for ch in expected_sha.lower()):
            raise ValueError("Expected commit SHA must be 40 hexadecimal characters.")
        if head != expected_sha.lower():
            raise RuntimeError("Checkout HEAD does not match the independently supplied commit SHA.")
    for path in ("tools/ci_free_local.py", "tests/test_ci_free_local.py"):
        git_stdout("ls-files", "--error-unmatch", "--", path)
    status = git_stdout("status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError("Checkout is not clean; tracked/untracked changes must be reviewed before validation.")
    print(f"REVISION: {head} (clean checkout; remote authenticity NOT_VERIFIED)")
    return head


def reject_duplicate_json_keys(pairs):
    """Reject ambiguous duplicate keys at every object nesting level."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def reject_non_json_constant(value):
    raise ValueError(f"non-JSON numeric constant: {value}")


def find_bash(*, windows=None):
    """On Windows avoid WSL's bash.exe when Git Bash is required."""
    if windows is None:
        windows = os.name == "nt"
    if not windows:
        return shutil.which("bash")
    git_exe = shutil.which("git")
    if git_exe:
        git_root = Path(git_exe).resolve().parent.parent
        candidate = git_root / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    bash = shutil.which("bash")
    if bash and "system32" not in str(Path(bash)).lower():
        return bash
    return None


def validate_json():
    checked = 0
    for path in sorted(ROOT.rglob("*.json")):
        if EXCLUDE.intersection(path.relative_to(ROOT).parts):
            continue
        if path.is_symlink():
            raise ValueError(f"JSON symlink not allowed: {path.relative_to(ROOT)}")
        with path.open(encoding="utf-8") as stream:
            json.load(
                stream,
                object_pairs_hook=reject_duplicate_json_keys,
                parse_constant=reject_non_json_constant,
            )
        checked += 1
    print(f"JSON validated: {checked} file(s)")


def isolated_smoke_port():
    """Select a short-lived local port rather than probing an existing Selma server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def validate_shell():
    bash = find_bash()
    if not bash:
        print("INCOMPLETE: Bash missing; shell checks and agent smoke test NOT_RUN.")
        print("Install Git Bash (Windows) or Bash, then rerun for full core verification.")
        return False
    scripts = sorted(
        p for p in ROOT.rglob("*.sh")
        if not EXCLUDE.intersection(p.relative_to(ROOT).parts)
    )
    for script in scripts:
        run([bash, "-n", script.relative_to(ROOT)], timeout=60)
    smoke_env = os.environ.copy()
    smoke_env["SELMA0_SMOKE_PORT_V1"] = str(isolated_smoke_port())
    run(
        [bash, "SELMA0_ANDROID_AGENT_V1/selma0_smoke_test_android_v1.sh"],
        timeout=SMOKE_TIMEOUT_SECONDS, env=smoke_env,
        cleanup_on_failure=True,
    )
    print(f"Bash syntax validated: {len(scripts)} file(s)")
    return True


def build_android():
    project = ROOT / "SELMA0_ANDROID_NATIVE_V1"
    if not project.is_dir():
        raise RuntimeError("Native Android project is missing.")
    if not shutil.which("java"):
        raise RuntimeError("Java 17 is needed on PATH for Android Gradle build.")
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk or not Path(sdk).is_dir():
        raise RuntimeError("Set ANDROID_HOME or ANDROID_SDK_ROOT to an installed Android SDK.")
    if not (project / "gradle/wrapper/gradle-wrapper.jar").is_file():
        raise RuntimeError("Trusted Gradle wrapper JAR is missing; refuse to substitute system Gradle.")
    apk = project / "app/build/outputs/apk/debug/app-debug.apk"
    checksum = apk.with_suffix(apk.suffix + ".sha256")
    if apk.is_symlink() or checksum.is_symlink():
        raise RuntimeError("APK or checksum output must not be a symlink.")
    # Remove only the prior generated debug artifact: a no-op build must not
    # count an old APK as a newly produced result.
    if apk.exists():
        if not apk.is_file():
            raise RuntimeError("Expected debug APK output path is not a file.")
        apk.unlink()
    if checksum.exists():
        checksum.unlink()
    tasks = [":app:lintDebug", ":app:testDebugUnitTest", ":app:assembleDebug"]
    if os.name == "nt":
        command = ["cmd", "/c", "gradlew.bat", "--no-daemon", *tasks]
    else:
        command = ["./gradlew", "--no-daemon", *tasks]
    run(command, cwd=project, timeout=ANDROID_TIMEOUT_SECONDS)
    if apk.is_symlink() or not apk.is_file():
        raise RuntimeError("Gradle returned without a newly generated regular debug APK.")
    try:
        with zipfile.ZipFile(apk) as archive:
            names = set(archive.namelist())
            required = {"AndroidManifest.xml", "resources.arsc", "classes.dex"}
            if not required.issubset(names):
                raise RuntimeError("APK is missing Android package components.")
            if archive.testzip() is not None:
                raise RuntimeError("APK ZIP integrity test failed.")
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise RuntimeError("APK is not a valid ZIP package.") from error
    digest = hashlib.sha256()
    with apk.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum.write_text(f"{digest.hexdigest()}  {apk.name}\n", encoding="ascii")
    print(f"APK: {apk}\nSHA256: {digest.hexdigest()}\nChecksum: {checksum}")
    print("APK ZIP/entries/hash validated; signature, installability, security and offline operation remain NOT_VERIFIED.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", action="store_true", help="Also build the debug Android APK (Java 17 and Android SDK required)")
    args = parser.parse_args()
    os.chdir(ROOT)
    if sys.version_info < (3, 12):
        parser.error("Python 3.12 or newer is required.")

    print("Selma local CI | independent of GitHub Actions | no hosted runner charges", flush=True)
    revision()
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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
