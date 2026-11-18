#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE="${SELMA0_BASE_V1:-$HOME/SELMA0_ANDROID_AGENT_V1}"
STATE="$BASE/.adult-mode-v1"
PID_FILE="$STATE/command-core.pid"
LOG_FILE="$STATE/command-core.log"
LLAMA="$BASE/selma0_llama_runtime_android_v1.sh"
AVATAR="$BASE/selma0_avatar_presence_android_v1.py"
RUNTIME="$BASE/selma0_runtime_device_crowrf_android_v1.py"
NATIVE_COMPONENT="ai.selma.companion/.MainActivity"

mkdir -p "$STATE"

fail() { printf 'SELMA0_ADULT_MODE_ERROR: %s\n' "$*" >&2; exit 1; }

core_running() {
  [ -f "$PID_FILE" ] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

avatar_ready() {
  python "$AVATAR" status 2>/dev/null | python -c '
import json,sys
try:
    value=json.load(sys.stdin)
    raise SystemExit(0 if value.get("available") else 1)
except Exception:
    raise SystemExit(1)
'
}

start_all() {
  export SELMA0_OFFLINE_ONLY_V1=1
  [ -x "$LLAMA" ] || fail "local llama runtime manager is missing: $LLAMA"
  [ -f "$AVATAR" ] || fail "avatar presence adapter is missing: $AVATAR"
  [ -f "$RUNTIME" ] || fail "Selma command runtime is missing: $RUNTIME"

  if ! avatar_ready; then
    fail "verified Adult Mode avatar pack is not installed; run: $0 install-pack /path/to/pack.zip"
  fi

  if ! "$LLAMA" status >/dev/null 2>&1; then
    "$LLAMA" start
  fi

  if core_running; then
    printf 'command_core=already_running pid=%s\n' "$(cat "$PID_FILE")"
  else
    nohup env SELMA0_OFFLINE_ONLY_V1=1 SELMA0_BASE_V1="$BASE"       python "$RUNTIME" >"$LOG_FILE" 2>&1 &
    printf '%s\n' "$!" >"$PID_FILE"
    sleep 1
    if ! core_running; then
      rm -f "$PID_FILE"
      fail "command core exited during startup; see $LOG_FILE"
    fi
    printf 'command_core=started pid=%s\n' "$(cat "$PID_FILE")"
  fi

  printf 'adult_mode_url=http://127.0.0.1:8765/adult-mode\n'
  printf 'offline_only=1\n'
}

stop_all() {
  if core_running; then
    local pid
    pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  "$LLAMA" stop >/dev/null 2>&1 || true
  printf 'adult_mode=stopped\n'
}

status_all() {
  printf 'offline_only=1\n'
  if core_running; then
    printf 'command_core=running pid=%s\n' "$(cat "$PID_FILE")"
  else
    printf 'command_core=stopped\n'
  fi
  "$LLAMA" status || true
  python "$AVATAR" status || true
}

install_pack() {
  local source="${1:-}"
  [ -n "$source" ] || fail "pack path is required"
  [ -f "$source" ] || fail "pack does not exist: $source"
  shift || true
  local trust=""
  if [ "${1:-}" = "--trust-on-first-use" ]; then
    trust="--trust-on-first-use"
  fi
  python "$AVATAR" install "$source" $trust
}

launch_native() {
  start_all
  if command -v am >/dev/null 2>&1; then
    am start -n "$NATIVE_COMPONENT" >/dev/null
    printf 'native_shell=launched\n'
  else
    printf 'native_shell=unavailable; open http://127.0.0.1:8765/adult-mode in a local browser\n'
  fi
}

usage() {
  cat <<EOF
Usage:
  $0 install-pack PACK.zip [--trust-on-first-use]
  $0 start
  $0 launch
  $0 status
  $0 stop

Adult Mode start/launch always forces SELMA0_OFFLINE_ONLY_V1=1.
It never downloads a model, avatar pack, voice, or remote fallback at runtime.
EOF
}

case "${1:-}" in
  install-pack) shift; install_pack "$@" ;;
  start) start_all ;;
  launch) launch_native ;;
  status) status_all ;;
  stop) stop_all ;;
  *) usage; exit 2 ;;
esac
