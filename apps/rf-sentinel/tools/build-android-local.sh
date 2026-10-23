#!/usr/bin/env bash
# Safe, manual Android build fallback when GitHub Actions does not start jobs.
set -euo pipefail
cd "$(dirname "$0")/.."
allow_network=0
if [[ "${1:-}" == "--allow-network" ]]; then allow_network=1; fi
if [[ $# -gt 1 ]] || { [[ $# -eq 1 ]] && [[ "${1}" != "--allow-network" ]]; }; then
  echo "Usage: bash tools/build-android-local.sh [--allow-network]" >&2
  exit 64
fi
command -v java >/dev/null || { echo "BLOCKED: JDK 17 required" >&2; exit 75; }
command -v gradle >/dev/null || { echo "BLOCKED: Gradle 8.9 required" >&2; exit 75; }
command -v python3 >/dev/null || { echo "BLOCKED: Python 3 required" >&2; exit 75; }
sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$sdk" || ! -f "$sdk/platforms/android-35/android.jar" ]]; then
  echo "BLOCKED: ANDROID_SDK_ROOT must point to a local SDK with platform 35" >&2
  exit 75
fi
echo "SOURCE_ONLY_CHECKS"
python3 -m unittest discover -s tests -v
if [[ "$allow_network" == 1 ]]; then
  echo "NETWORK_AUTHORIZED_FOR_GRADLE_DEPENDENCIES"
  gradle --no-daemon :app:assembleDebug
else
  echo "GRADLE_OFFLINE_MODE (use --allow-network only after reviewing dependency sources)"
  gradle --offline --no-daemon :app:assembleDebug
fi
python3 tools/verify_apk.py app/build/outputs/apk/debug/app-debug.apk
echo "BUILD ARTIFACT EXISTS: physical device install, permission and sensing QA NOT VERIFIED"
