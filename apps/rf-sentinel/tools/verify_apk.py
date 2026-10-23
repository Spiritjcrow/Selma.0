#!/usr/bin/env python3
"""Structure/hash inspection of a locally built debug APK, NOT install or sensor QA."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import zipfile

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
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "archive_test": "PASS",
        "device_install": "NOT_RUN",
        "radio_observations": "NOT_RUN",
        "signature": "NOT_VERIFIED",
    }
    signer = shutil.which("apksigner")
    if signer:
        proc = subprocess.run([signer, "verify", "--verbose", str(path)],
                              text=True, capture_output=True, timeout=25, check=False)
        result["signature"] = "PASS" if proc.returncode == 0 else "FAIL"
        if proc.returncode:
            print(json.dumps(result, indent=2))
            return 1
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
