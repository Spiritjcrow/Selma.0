#!/usr/bin/env bash
# SelmaOS build validation: never claim an APK was built unless it exists.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

usage() {
  cat <<'USAGE'
SelmaOS reproducible build
  bash build.sh --agent    Offline-capable Python checks, tests and smoke test (default)
  bash build.sh --android  Build native Android debug APK (JDK17 + Android SDK required)
  bash build.sh --all      Run both; fail if either cannot complete
  bash build.sh --help
This script never installs dependencies, elevates permissions, contacts the router,
or assumes a particular SSID, gateway, carrier, or LAN IP address.
USAGE
}

mode="${1:---agent}"
if [ "$#" -gt 1 ]; then usage >&2; exit 2; fi
case "$mode" in
  --help|-h) usage; exit 0 ;;
  --agent|--android|--all) ;;
  *) usage >&2; exit 2 ;;
esac

check_agent() {
  command -v python3 >/dev/null || {
    echo "ERROR: Python 3 is required. No environment changes were made." >&2
    return 1
  }
  echo "[SelmaOS] Checking agent sources and scripts..."
  python3 -m compileall -q SELMA0_ANDROID_AGENT_V1 adapters core tests tools
  while IFS= read -r -d '' script; do
    bash -n "$script"
  done < <(find SELMA0_ANDROID_AGENT_V1 -type f -name '*.sh' -print0)
  echo "[SelmaOS] Running offline command core and network diagnostic tests..."
  python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v
  python3 -m unittest discover -s tests -p 'test_*.py' -v
  python3 tools/generate_support_matrix.py --check
  bash SELMA0_ANDROID_AGENT_V1/selma0_smoke_test_android_v1.sh
  echo "[SelmaOS] Agent tests and isolated runtime smoke test passed."
}

build_android() {
  if [ ! -f SELMA0_ANDROID_NATIVE_V1/gradlew ]; then
    echo "ERROR: Android Gradle wrapper missing." >&2; return 1
  fi
  command -v java >/dev/null || {
    echo "ERROR: JDK 17 required for Android build; use cloud Android workflow." >&2
    return 1
  }
  sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [ -z "$sdk" ] || [ ! -d "$sdk" ]; then
    echo "ERROR: Android SDK not configured; use cloud Android workflow." >&2
    return 1
  fi
  echo "[SelmaOS] Building native APK using pinned Gradle wrapper..."
  (
    cd SELMA0_ANDROID_NATIVE_V1
    bash ./gradlew --no-daemon :app:lintDebug :app:testDebugUnitTest :app:assembleDebug
  )
  apk="SELMA0_ANDROID_NATIVE_V1/app/build/outputs/apk/debug/app-debug.apk"
  if [ ! -s "$apk" ]; then
    echo "ERROR: Gradle did not produce a nonempty APK." >&2
    return 1
  fi
  echo "[SelmaOS] Android debug APK built: $apk"
  if command -v sha256sum >/dev/null; then
    sha256sum "$apk"
  fi
}

case "$mode" in
  --agent) check_agent ;;
  --android) build_android ;;
  --all) check_agent; build_android ;;
esac
echo "[SelmaOS] Completed requested target: $mode"
