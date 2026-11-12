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
java_details="$(java -XshowSettings:properties -version 2>&1 || true)"
java_spec="$(sed -n 's/^[[:space:]]*java\.specification\.version = //p' <<< "$java_details" | head -n 1)"
if [[ "$java_spec" != "17" ]]; then
  echo "BLOCKED: JDK 17 required; found ${java_spec:-unknown}" >&2
  exit 75
fi
gradle_details="$(gradle --version 2>&1 || true)"
gradle_version="$(sed -n 's/^Gradle //p' <<< "$gradle_details" | head -n 1)"
if [[ "$gradle_version" != "8.9" ]]; then
  echo "BLOCKED: Gradle 8.9 required; found ${gradle_version:-unknown}" >&2
  exit 75
fi
sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$sdk" || ! -f "$sdk/platforms/android-35/android.jar" ]]; then
  echo "BLOCKED: ANDROID_SDK_ROOT must point to a local SDK with platform 35" >&2
  exit 75
fi
build_tools="$sdk/build-tools/35.0.0"
resolve_build_tool() {
  local name="$1" override_name="$2" override candidate
  override="${!override_name:-}"
  if [[ -n "$override" ]]; then
    if [[ ! -f "$override" || ! -x "$override" ]]; then
      echo "BLOCKED: $override_name must name an executable file" >&2
      return 75
    fi
    printf '%s\n' "$override"
    return
  fi
  for candidate in "$build_tools/$name" "$build_tools/$name.exe" "$build_tools/$name.bat"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  candidate="$(command -v "$name" || true)"
  if [[ -n "$candidate" && -f "$candidate" && -x "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return
  fi
  echo "BLOCKED: Android build-tools 35.0.0 or an executable $name override is required" >&2
  return 75
}
aapt2_path="$(resolve_build_tool aapt2 RF_SENTINEL_AAPT2)"
apksigner_path="$(resolve_build_tool apksigner RF_SENTINEL_APKSIGNER)"
export RF_SENTINEL_AAPT2="$aapt2_path"
export RF_SENTINEL_APKSIGNER="$apksigner_path"
gradle_args=(
  --no-daemon
  "-Pandroid.aapt2FromMavenOverride=$aapt2_path"
  :app:lintDebug
  :app:testDebugUnitTest
  :app:assembleDebug
)
echo "SOURCE_ONLY_CHECKS"
python3 -m unittest discover -s tests -v
if [[ "$allow_network" == 1 ]]; then
  echo "NETWORK_AUTHORIZED_FOR_GRADLE_DEPENDENCIES"
  gradle "${gradle_args[@]}"
else
  echo "GRADLE_OFFLINE_MODE (use --allow-network only after reviewing dependency sources)"
  gradle --offline "${gradle_args[@]}"
fi
evidence_path="${RF_SENTINEL_EVIDENCE_PATH:-app/build/outputs/apk/debug/rf-sentinel-debug-evidence.json}"
mkdir -p "$(dirname "$evidence_path")"
evidence_tmp="$(mktemp "${evidence_path}.tmp.XXXXXX")"
cleanup_evidence() { rm -f -- "$evidence_tmp"; }
trap cleanup_evidence EXIT
python3 tools/verify_apk.py app/build/outputs/apk/debug/app-debug.apk | tee "$evidence_tmp"
if [[ ! -s "$evidence_tmp" ]]; then
  echo "FAIL: APK verification produced no evidence" >&2
  exit 1
fi
mv -f -- "$evidence_tmp" "$evidence_path"
trap - EXIT
echo "VERIFICATION EVIDENCE: $evidence_path"
echo "BUILD ARTIFACT EXISTS: physical device install, permission and sensing QA NOT VERIFIED"
