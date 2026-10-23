# Fallback build and evidence protocol

## Why it exists
The owned GitHub Actions environment has produced repeated `startup_failure`
runs with **zero jobs** (issue #26). A new workflow file cannot fix a
runner-admission failure by itself.

## Self-hosted desktop / Chromebook Linux alternative
Requires a configured **Android SDK platform 35**, **JDK 17**, **Gradle 8.9**,
and Python 3.8+ (initial Gradle dependency download may require internet).

From `apps/rf-sentinel/`:

```bash
bash tools/build-android-local.sh --allow-network
# Later cached builds may use:
bash tools/build-android-local.sh
```

`--allow-network` is an explicit opt-in for Gradle artifact downloads.
The script does not call `apt upgrade`, use `sudo`, edit Android device
settings or modify account credentials. No background monitoring starts.

If the build succeeds, preserve the APK SHA256 and the script's console
output. An APK archive/hash/signature verification is NOT a device test.

## Android 11/13+ device acceptance still required

- Install the same hashed APK from a locally trusted build.
- Check permission-granted AND permission-denied paths, Location toggle,
  Wi-Fi disabled, Bluetooth disabled, BLE scanning stop and Android throttling.
- Compare exported CSV to the actual observations and ensure it contains no
  SSID, MAC, or BLE device identifiers; inspect app networking in airplane mode.
- Verify performance, battery use, and manual stop on an actual target phone.
- Any model/sensor for genuine CSI presence sensing requires separate
  compatible ESP32 hardware, calibration and known-ground-truth study.
- Do not claim human count, cardiac telemetry, thoughts, threat scoring or
  attack intentions from Wi-Fi/BLE RSSI scans.

If SDK/Gradle are unavailable, run portable source-only checks:
`python3 -m unittest discover -s tests -v`, and keep APK/device gates BLOCKED.

## GitLab / third-party CI alternative
See `ci/gitlab-rf-sentinel-example.yml` for a source-check reference.
It is NOT active until an authorized GitLab repository and runner exist.
No account, subscription, release, package signing or public deployment
is created by this fallback.
