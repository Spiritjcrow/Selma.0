#!/usr/bin/env python3
"""Structure/hash inspection of a locally built debug APK, NOT install or sensor QA."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile


EXPECTED_PACKAGE_ID = "org.selma.rfsentinel"
EXPECTED_MIN_SDK = "30"
EXPECTED_TARGET_SDK = "35"
EXPECTED_LAUNCHABLE_ACTIVITY = "org.selma.rfsentinel.MainActivity"
EXPECTED_VERSION_CODE = "2"
EXPECTED_VERSION_NAME = "0.2-source"
OPTIONAL_RADIO_FEATURES = (
    "android.hardware.wifi",
    "android.hardware.bluetooth_le",
)
EXPECTED_PERMISSIONS = frozenset({
    "android.permission.ACCESS_WIFI_STATE",
    "android.permission.CHANGE_WIFI_STATE",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.BLUETOOTH",
    "android.permission.BLUETOOTH_ADMIN",
    "android.permission.BLUETOOTH_SCAN",
})


def find_build_tool(name):
    override = os.environ.get("RF_SENTINEL_" + name.upper())
    if override:
        path = pathlib.Path(override)
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
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


def badging_has_feature(output, kind, feature):
    pattern = rf"^{re.escape(kind)}(?:: name=|:)'{re.escape(feature)}'"
    return re.search(pattern, output, re.MULTILINE) is not None


def parse_permissions(output):
    return frozenset(re.findall(
        r"^uses-permission(?:: name=|:)'([^']+)'",
        output,
        re.MULTILINE,
    ))


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
        "version_code": "NOT_VERIFIED",
        "version_name": "NOT_VERIFIED",
        "internet_permission": "NOT_VERIFIED",
        "permission_contract": "NOT_VERIFIED",
        "min_sdk": "NOT_VERIFIED",
        "target_sdk": "NOT_VERIFIED",
        "launchable_activity": "NOT_VERIFIED",
        "radio_hardware_optional": "NOT_VERIFIED",
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

    permissions = run_tool([aapt2, "dump", "permissions", str(path)])
    if permissions is None or permissions.returncode != 0:
        result["internet_permission"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: AAPT2 could not read APK permissions", file=sys.stderr)
        return 1
    if "android.permission.INTERNET" in permissions.stdout:
        result["internet_permission"] = "PRESENT"
        print(json.dumps(result, indent=2))
        print("FAIL: APK violates offline-first policy with INTERNET permission", file=sys.stderr)
        return 1
    result["internet_permission"] = "ABSENT"
    observed_permissions = parse_permissions(permissions.stdout)
    if observed_permissions != EXPECTED_PERMISSIONS:
        result["permission_contract"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: APK permission set differs from reviewed contract", file=sys.stderr)
        return 1
    result["permission_contract"] = "PASS"

    badging = run_tool([aapt2, "dump", "badging", str(path)])
    if badging is None or badging.returncode != 0:
        result["min_sdk"] = "FAIL"
        result["target_sdk"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: AAPT2 could not read APK SDK compatibility", file=sys.stderr)
        return 1
    min_sdk = re.search(r"^sdkVersion:'(\d+)'$", badging.stdout, re.MULTILINE)
    target_sdk = re.search(r"^targetSdkVersion:'(\d+)'$", badging.stdout, re.MULTILINE)
    if min_sdk is None or target_sdk is None:
        result["min_sdk"] = "FAIL"
        result["target_sdk"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: APK SDK compatibility evidence is incomplete", file=sys.stderr)
        return 1
    result["min_sdk"] = min_sdk.group(1)
    result["target_sdk"] = target_sdk.group(1)
    if (result["min_sdk"] != EXPECTED_MIN_SDK or
            result["target_sdk"] != EXPECTED_TARGET_SDK):
        print(json.dumps(result, indent=2))
        print("FAIL: unexpected APK SDK compatibility", file=sys.stderr)
        return 1
    launchable = re.search(
        r"^launchable(?:-activity:| activity) name='([^']+)'",
        badging.stdout,
        re.MULTILINE,
    )
    if launchable is None:
        result["launchable_activity"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: APK has no verified launchable activity", file=sys.stderr)
        return 1
    result["launchable_activity"] = launchable.group(1)
    if result["launchable_activity"] != EXPECTED_LAUNCHABLE_ACTIVITY:
        print(json.dumps(result, indent=2))
        print("FAIL: unexpected APK launchable activity", file=sys.stderr)
        return 1
    invalid_features = [
        feature for feature in OPTIONAL_RADIO_FEATURES
        if (badging_has_feature(badging.stdout, "uses-feature", feature) or
            not badging_has_feature(
                badging.stdout, "uses-feature-not-required", feature
            ))
    ]
    if invalid_features:
        result["radio_hardware_optional"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: APK does not preserve optional radio hardware", file=sys.stderr)
        return 1
    result["radio_hardware_optional"] = "PASS"
    package_badging = re.search(
        r"^package: name='[^']+' versionCode='([^']+)' versionName='([^']+)'",
        badging.stdout,
        re.MULTILINE,
    )
    if package_badging is None:
        result["version_code"] = "FAIL"
        result["version_name"] = "FAIL"
        print(json.dumps(result, indent=2))
        print("FAIL: APK version evidence is incomplete", file=sys.stderr)
        return 1
    result["version_code"] = package_badging.group(1)
    result["version_name"] = package_badging.group(2)
    if (result["version_code"] != EXPECTED_VERSION_CODE or
            result["version_name"] != EXPECTED_VERSION_NAME):
        print(json.dumps(result, indent=2))
        print("FAIL: unexpected APK version metadata", file=sys.stderr)
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
