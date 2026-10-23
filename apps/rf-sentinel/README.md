# SelmaOS RF Sentinel, Android 11+ source-only alpha

Offline-first Android app. Manual Wi-Fi AP and BLE advertisement survey, aggregate RSSI/count
measurements, in-memory reference baseline, CSV export through Android document picker.
No internet permission, no root, no background tracking, no device identifiers exported.

**Not a surveillance or threat classifier.** Wi-Fi AP/BLE counts cannot establish human or
pet presence, pulse, speech, brain activity or intent. RF change index is an unvalidated
numeric observation and must never be interpreted as danger or probability.

Build: Android SDK 35 + JDK 17 + Gradle 8.9, from this folder:
`gradle :app:assembleDebug`.

Pre-release acceptance requires an actual GitHub Actions *job* and signed-off
physical Android 11/13+ device QA: Wi-Fi/BLE permissions denied, location/radios off,
throttle/cached reads, BLE stop, privacy/export, airplane mode and battery draw.
No CI job or debug APK counts as device QA. CI startup_failure / zero jobs on repo issue #26
must be treated as an external admission blocker, not a successful build.

Fallback: extract the conversation artifact RF Sentinel Autopilot v0.2 and run
`python3 tools/autopilot.py run` on a supported developer machine. It provides
Python/C++/Kotlin source checks, NOT an Android APK without the SDK.
See repository issue #81 for queued acceptance gates.
