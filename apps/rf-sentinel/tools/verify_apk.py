#!/usr/bin/env python3
"""Structure/hash inspection of a locally built debug APK, NOT install or sensor QA."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile


EXPECTED_PACKAGE_ID = "org.selma.rfsentinel"


def find_build_tool(name):
    tool = shutil.which(name)
    if tool:
        return tool
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if not sdk:
        return None
    build_tools = pathlib.Path(sdk) / "build-tools" / "35.0.0"
    for filename in (name, name + ".bat"):
        candidate = build_tools / filename
        if candidate.is_file():
            return str(candidate)
    return None


def run_tool(command):
    try:
        return subprocess.run(command, text=True, capture_output=True,
                              timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv):
    if len(argv) != 2:
        print("Usage: python3 tools/verify_apk.py PATH_TO_DEBUG_APK", file=sys.stderr)
        return 64
    path = pathlib.Path(argv[1])
    if not path.is_file():
        print("BLOCKED: real APK not present: " + str(path), file=sys.stderr)
        return 75
    with zipfile.ZipFile(str(path)) as apk:
        bad = apk.testzip()
        if bad is not None:
            print("FAIL: corrupt ZIP member " + bad, file=sys.stderr)
            return 1
        names = set(apk.namelist())
        required = {"AndroidManifest.xml", "classes.dex"}
        missing = required - names
        if missing:
            print("FAIL: missing APK entries: " + ",".join(sorted(missing)), file=sys.stderr)
            return 1
    result = {
        "apk": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "archive_test": "PASS",
        "package_id": "NOT_VERIFIED",
        "device_install": "NOT_RUN",
        "radio_observations": "NOT_RUN",
        "signature": "NOT_VERIFIED",
    }
    aapt2 = find_build_tool("aapt2")
    if not aapt2:
        result["package_id"] = "BLOCKED"
        print(json.dumps(result, indent=2))
        print("BLOCKED: AAPT2 is required to verify APK package identity", file=sys.stderr)
        return 75
    package = run_tool([aapt2, "dump", "packagename", str(path)])
    if package is None or package.returncode != 0:
        result["package_id"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: AAPT2 could not read APK package identity", file=sys.stderr)
        return 1
    result["package_id"] = package.stdout.strip()
    if result["package_id"] != EXPECTED_PACKAGE_ID:
        print(json.dumps(result, indent=2))
        print("FAIL: unexpected APK package identity", file=sys.stderr)
        return 1

    signer = find_build_tool("apksigner")
    if not signer:
        result["signature"] = "BLOCKED"
        print(json.dumps(result, indent=2))
        print("BLOCKED: apksigner is required for APK evidence", file=sys.stderr)
        return 75
    proc = run_tool([signer, "verify", "--verbose", str(path)])
    if proc is None:
        result["signature"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: apksigner could not execute", file=sys.stderr)
        return 1
    result["signature"] = "PASS" if proc.returncode == 0 else "FAIL"
    print(json.dumps(result, indent=2))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
