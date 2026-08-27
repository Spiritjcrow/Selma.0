#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SELMA0_HOME_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
PROFILE="$HOME/.config/selma0/moto-g-play-2023.env"

MODEL="$(getprop ro.product.model 2>/dev/null || true)"
ANDROID_RELEASE="$(getprop ro.build.version.release 2>/dev/null || true)"
SDK="$(getprop ro.build.version.sdk 2>/dev/null || true)"
ARCH="$(uname -m 2>/dev/null || true)"
FREE_KB="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')"
FREE_KB="${FREE_KB:-0}"

printf '=== Selma.0 Moto G Play 2023 validation ===\n'
printf 'Model: %s\nAndroid: %s (SDK %s)\nArch: %s\nFree storage: %s MB\n' \
  "${MODEL:-unknown}" "${ANDROID_RELEASE:-unknown}" "${SDK:-unknown}" "${ARCH:-unknown}" "$((FREE_KB / 1024))"

[ -d "$SELMA0_HOME_V1" ] || { echo "FAIL: runtime directory missing"; exit 10; }
[ -f "$PROFILE" ] || { echo "FAIL: Moto profile missing"; exit 11; }
[ -x "$SELMA0_HOME_V1/selma0_start_android_v1.sh" ] || { echo "FAIL: start script missing"; exit 12; }

. "$PROFILE"

echo "Python: $(python --version 2>&1)"
python -m compileall -q "$SELMA0_HOME_V1"

echo "Running command-core software smoke test..."
"$SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"

if command -v termux-wifi-scaninfo >/dev/null 2>&1; then
  echo "Termux:API Wi-Fi CLI: present"
else
  echo "Termux:API Wi-Fi CLI: unavailable; install/authorize the Termux:API companion for hardware Wi-Fi acquisition."
fi

if command -v termux-open-url >/dev/null 2>&1; then
  echo "Browser launcher: present"
else
  echo "Browser launcher: unavailable; open http://127.0.0.1:8765 manually after starting Selma.0."
fi

if command -v curl >/dev/null 2>&1; then
  echo "curl: present"
else
  echo "curl: not installed; smoke validation used the runtime's existing test path."
fi

cat <<EOF
PASS: Moto G Play 2023 rootless runtime validation completed.
Start: $SELMA0_HOME_V1/selma0_start_android_v1.sh
UI: http://127.0.0.1:8765
Local LLM endpoint expected: ${SELMA0_LOCAL_BASE_URL_V1:-http://127.0.0.1:8080/v1}
EOF
