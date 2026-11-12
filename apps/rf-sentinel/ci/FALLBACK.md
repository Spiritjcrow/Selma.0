# Fallback build and evidence protocol

## Why it exists
The owned GitHub Actions environment has produced repeated `startup_failure`
runs with **zero jobs** (issue #26). A new workflow file cannot fix a
runner-admission failure by itself.

## Hosted fallback pre-submit guard

Before starting a manual Codemagic or other hosted build, require the UI to show
all three exact values:

- workflow: `RF Sentinel Android debug verification`
- branch: `feature/rf-sentinel-android-ci-20261023`
- full source commit: the current PR #82 head from `git rev-parse HEAD`

Do not submit when the UI hides, truncates, resets, or changes any value. After
submission, open the new build detail page and compare its workflow, branch and
full commit again before treating it as RF Sentinel evidence. If any value
mismatches, stop that build if the authenticated owner controls it; do not retry
until the selector state can be independently verified. Never reuse an artifact
from `main`, another workflow, or an earlier commit as evidence for the current
PR head.

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

## Termux on Android (manual, no root)

Install only the local prerequisites; this does not change device OS settings:

```bash
pkg update
pkg install git python openjdk-17 curl unzip aapt2 apksigner
export JAVA_HOME="$PREFIX/lib/jvm/java-17-openjdk"
export PATH="$JAVA_HOME/bin:$PREFIX/bin:$PATH"
```

Install the pinned Gradle 8.9 distribution after verifying its official checksum:

```bash
cd "$HOME"
curl -fL --proto '=https' --tlsv1.2 \
  -o gradle-8.9-bin.zip https://services.gradle.org/distributions/gradle-8.9-bin.zip
printf '%s  %s\n' \
  d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab \
  gradle-8.9-bin.zip | sha256sum -c -
unzip -q gradle-8.9-bin.zip
export PATH="$HOME/gradle-8.9/bin:$PATH"
```

A trusted ARM-compatible Android SDK platform 35 is still required. Set
`ANDROID_SDK_ROOT` to that local SDK and verify that
`$ANDROID_SDK_ROOT/platforms/android-35/android.jar` exists. Google's Linux
Android Studio package does not support Linux ARM CPUs, so do not run an
unreviewed installer or pipe a download into a shell to bypass that limit.

Use the Termux-native build tools explicitly, then run the same gates:

```bash
export RF_SENTINEL_AAPT2="$(command -v aapt2)"
export RF_SENTINEL_APKSIGNER="$(command -v apksigner)"
cd /path/to/Selma.0/apps/rf-sentinel
bash tools/build-android-local.sh --allow-network
```

The script passes the reviewed native `aapt2` path to Gradle and reuses both
overrides for APK verification. Missing, non-executable, or incompatible tools
fail closed; source-only checks do not count as an APK build.

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
