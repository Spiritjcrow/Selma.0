#!/usr/bin/env python3
"""EcoFix RescueHost: read-only ADB/Fastboot diagnostic report.
Requires Android platform-tools on the machine executing this script.
No unlocking, flashing, resets, shell modifications, or account operations.
"""
import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 12

def run(*argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT, check=False)
        return {"exit_code": p.returncode, "stdout": p.stdout.strip()[:12000], "stderr": p.stderr.strip()[:2000]}
    except subprocess.TimeoutExpired:
        return {"error": "command timed out"}
    except OSError as exc:
        return {"error": str(exc)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="rescuehost-report.json")
    args = parser.parse_args()
    report = {"schema": "ecofix.rescuehost.diagnostic.v1",
              "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "mode": "read_only", "tools": {}, "devices": []}
    adb = shutil.which("adb")
    fastboot = shutil.which("fastboot")
    if adb:
        report["tools"]["adb_version"] = run(adb, "version")
        listing = run(adb, "devices", "-l")
        report["tools"]["adb_devices"] = listing
        for line in listing.get("stdout", "").splitlines()[1:]:
            cols = line.split()
            if len(cols) < 2:
                continue
            serial, state = cols[:2]
            item = {"transport": "adb", "serial_sha256": hashlib.sha256(serial.encode()).hexdigest(),
                    "state": state}
            if state == "device":
                # Device has already authorized ADB. Read-only properties only.
                for key in ("ro.product.manufacturer", "ro.product.model",
                            "ro.build.version.release", "ro.build.fingerprint"):
                    item[key] = run(adb, "-s", serial, "shell", "getprop", key).get("stdout", "")
            report["devices"].append(item)
    else:
        report["tools"]["adb"] = "not installed"
    if fastboot:
        report["tools"]["fastboot_version"] = run(fastboot, "--version")
        listing = run(fastboot, "devices")
        report["tools"]["fastboot_devices"] = listing
        for line in listing.get("stdout", "").splitlines():
            cols = line.split()
            if len(cols) >= 2:
                report["devices"].append({
                    "transport": "fastboot",
                    "serial_sha256": hashlib.sha256(cols[0].encode()).hexdigest(),
                    "state": cols[1]})
    else:
        report["tools"]["fastboot"] = "not installed"
    path = Path(args.output)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Report written: {path} | detected devices: {len(report['devices'])}")
    if not adb and not fastboot:
        print("Install official Android SDK Platform-Tools; neither executable is available.", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
