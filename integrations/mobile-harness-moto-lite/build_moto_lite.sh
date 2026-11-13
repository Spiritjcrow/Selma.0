#!/usr/bin/env bash
set -euo pipefail
repo=${1:-Mobile-Harness}
if [[ ! -d "$repo/.git" ]]; then
  git clone --depth 1 --branch v1.0.7 https://github.com/techjarves/Mobile-Harness.git "$repo"
fi
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo"
git submodule update --init --recursive
python3 "$script_dir/apply_moto_lite.py"
./gradlew -PmotoLite=true :app:assembleOnlineDebug
printf '\nDebug APK (if build succeeds): %s\n' "$PWD/app/build/outputs/apk/online/debug/app-online-debug.apk"