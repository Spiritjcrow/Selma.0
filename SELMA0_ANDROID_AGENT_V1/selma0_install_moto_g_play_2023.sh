#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
SELMA0_HOME_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
PROFILE_DIR="$HOME/.config/selma0"
PROFILE_FILE="$PROFILE_DIR/moto-g-play-2023.env"

MODEL="$(getprop ro.product.model 2>/dev/null || true)"
DEVICE="$(getprop ro.product.device 2>/dev/null || true)"
ANDROID_RELEASE="$(getprop ro.build.version.release 2>/dev/null || true)"
SDK="$(getprop ro.build.version.sdk 2>/dev/null || true)"
ARCH="$(uname -m 2>/dev/null || true)"
FREE_KB="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')"
FREE_KB="${FREE_KB:-0}"

printf 'Selma.0 Moto G Play 2023 installer\n'
printf 'Model: %s\nDevice: %s\nAndroid: %s (SDK %s)\nArch: %s\nFree storage: %s MB\n' \
  "${MODEL:-unknown}" "${DEVICE:-unknown}" "${ANDROID_RELEASE:-unknown}" "${SDK:-unknown}" "${ARCH:-unknown}" "$((FREE_KB / 1024))"

if [ -n "$SDK" ] && [ "$SDK" -lt 31 ]; then
  echo "Android SDK $SDK is below the supported Android 12+ rootless profile."
  exit 2
fi

case "$ARCH" in
  aarch64|arm64*) ;;
  *) echo "Warning: expected ARM64/aarch64 for the Moto G Play 2023; continuing with detected $ARCH." ;;
esac

# Keep enough headroom for Termux package updates, SQLite state, logs, and runtime data.
if [ "$FREE_KB" -lt 262144 ]; then
  echo "At least 256 MB free storage is required before installing Selma.0."
  exit 3
fi

mkdir -p "$PROFILE_DIR"
cat > "$PROFILE_FILE" <<'EOF'
export SELMA0_DEVICE_PROFILE_V1="moto-g-play-2023"
export SELMA0_BASE_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
export SELMA0_HOST_V1="127.0.0.1"
export SELMA0_PORT_V1="8765"
export SELMA0_LOCAL_BASE_URL_V1="http://127.0.0.1:8080/v1"
export SELMA0_LOCAL_MODEL_V1="selma0-local"
export SELMA0_LLM_TIMEOUT_V1="30"
export PYTHONDONTWRITEBYTECODE="1"
EOF
chmod 600 "$PROFILE_FILE"

"$SOURCE_DIR/selma0_bootstrap_termux_android_v1.sh"

cat > "$SELMA0_HOME_V1/selma0_start_android_v1.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
PROFILE="$HOME/.config/selma0/moto-g-play-2023.env"
[ -f "$PROFILE" ] && . "$PROFILE"
cd "$HOME/SELMA0_ANDROID_AGENT_V1"
exec python selma0_runtime_device_crowrf_android_v1.py
EOF
chmod +x "$SELMA0_HOME_V1/selma0_start_android_v1.sh"

cp -f "$SOURCE_DIR/selma0_validate_moto_g_play_2023.sh" "$SELMA0_HOME_V1/selma0_validate_moto_g_play_2023.sh"
chmod +x "$SELMA0_HOME_V1/selma0_validate_moto_g_play_2023.sh"

python -m compileall -q "$SELMA0_HOME_V1"
"$SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"

cat <<EOF

Selma.0 Moto G Play 2023 profile installed.
Runtime: $SELMA0_HOME_V1
Profile: $PROFILE_FILE
Validate: $SELMA0_HOME_V1/selma0_validate_moto_g_play_2023.sh
Start: $SELMA0_HOME_V1/selma0_start_android_v1.sh
UI: http://127.0.0.1:8765

The UI/runtime works without root. Conversational inference requires either a local OpenAI-compatible server at 127.0.0.1:8080/v1 or explicitly configured online fallback variables.
EOF
