#!/usr/bin/env bash
# EmberBot v2.0 one-command Docker/Buildozer APK build.
# Tested: Bash syntax and Python tests. APK compilation requires a Linux host
# with network-enabled Docker; GitHub Actions is not required.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'ERROR: Python 3 is required to run preflight tests.' >&2
  exit 2
fi
python3 -m compileall -q main.py ember_engine.py tests
python3 -m unittest discover -s tests -v

if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'ERROR: Docker is not installed. Use a cloud Linux workspace with Docker.' >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  printf '%s\n' 'ERROR: Docker daemon is unavailable. Check permissions/runner service.' >&2
  exit 2
fi

# Uses the official Buildozer Docker image; no Termux or ADB.
# Download/compile duration and cost depend on the host and plan.
docker run --rm \
  --volume "$ROOT:/home/user/hostcwd" \
  --workdir /home/user/hostcwd \
  kivy/buildozer:latest android debug

mapfile -t apks < <(find bin -maxdepth 1 -type f -name '*.apk' | sort)
if (( ${#apks[@]} == 0 )); then
  printf '%s\n' 'FAIL: Buildozer exited without producing an APK.' >&2
  exit 1
fi
for apk in "${apks[@]}"; do
  test -s "$apk"
  if command -v unzip >/dev/null 2>&1; then
    unzip -tq "$apk"
    unzip -Z1 "$apk" | grep -Fxq 'AndroidManifest.xml'
  fi
  sha256sum "$apk"
  printf 'APK BUILT: %s\n' "$apk"
done

printf '%s\n' 'ANDROID DEVICE INSTALL AND RUNTIME FUNCTIONAL TEST NOT YET PERFORMED.'
