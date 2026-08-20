#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SELMA0_BASE_V1="${SELMA0_BASE_V1:-$HOME/SELMA0_ANDROID_AGENT_V1}"
STATE_DIR="${SELMA0_LLAMA_STATE_DIR_V1:-$SELMA0_BASE_V1/.llama-runtime-v1}"
MODEL_DIR="${SELMA0_MODEL_DIR_V1:-$SELMA0_BASE_V1/models}"
LLAMA_SRC="${SELMA0_LLAMA_SRC_V1:-$SELMA0_BASE_V1/vendor/llama.cpp}"
SERVER_BIN="${SELMA0_LLAMA_SERVER_V1:-$LLAMA_SRC/build/bin/llama-server}"
PID_FILE="$STATE_DIR/server.pid"
LOG_FILE="$STATE_DIR/server.log"
MODEL_FILE_STATE="$STATE_DIR/model.path"
HOST="127.0.0.1"
PORT="8080"

mkdir -p "$STATE_DIR" "$MODEL_DIR"

fail() { printf 'SELMA0_LLAMA_ERROR: %s\n' "$*" >&2; exit 1; }

mem_available_bytes() {
  awk '/MemAvailable:/ {print $2 * 1024; found=1} END {if (!found) print 0}' /proc/meminfo 2>/dev/null || printf '0\n'
}

storage_available_bytes() {
  df -Pk "$MODEL_DIR" 2>/dev/null | awk 'NR==2 {print $4 * 1024}' || printf '0\n'
}

profile_ctx() {
  local mem
  mem="$(mem_available_bytes)"
  if [ "$mem" -ge 6442450944 ]; then printf '4096\n'
  elif [ "$mem" -ge 4294967296 ]; then printf '3072\n'
  elif [ "$mem" -ge 2684354560 ]; then printf '2048\n'
  else printf '1024\n'; fi
}

select_model() {
  if [ -n "${SELMA0_MODEL_V1:-}" ]; then
    [ -f "$SELMA0_MODEL_V1" ] || fail "Configured model does not exist: $SELMA0_MODEL_V1"
    printf '%s\n' "$SELMA0_MODEL_V1"
    return
  fi

  local mem budget candidate size
  mem="$(mem_available_bytes)"
  [ "$mem" -gt 0 ] || fail "Unable to determine available RAM"
  budget=$((mem * 45 / 100))
  candidate=""

  while IFS= read -r path; do
    [ -f "$path" ] || continue
    size="$(wc -c < "$path")"
    if [ "$size" -le "$budget" ]; then
      candidate="$path"
      break
    fi
  done < <(find "$MODEL_DIR" -maxdepth 1 -type f -name '*.gguf' -print0 | xargs -0 -r ls -Sr)

  [ -n "$candidate" ] || fail "No GGUF model in $MODEL_DIR fits the conservative RAM budget ($budget bytes). Set SELMA0_MODEL_V1 to override."
  printf '%s\n' "$candidate"
}

profile() {
  local mem disk ctx model model_size
  mem="$(mem_available_bytes)"
  disk="$(storage_available_bytes)"
  ctx="$(profile_ctx)"
  model="$(select_model)"
  model_size="$(wc -c < "$model")"
  printf 'ram_available_bytes=%s\n' "$mem"
  printf 'storage_available_bytes=%s\n' "$disk"
  printf 'context_tokens=%s\n' "$ctx"
  printf 'model=%s\n' "$model"
  printf 'model_bytes=%s\n' "$model_size"
}

install_runtime() {
  command -v git >/dev/null 2>&1 || fail "git is required"
  command -v cmake >/dev/null 2>&1 || fail "cmake is required"
  command -v make >/dev/null 2>&1 || fail "make is required"

  if [ ! -d "$LLAMA_SRC/.git" ]; then
    mkdir -p "$(dirname "$LLAMA_SRC")"
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$LLAMA_SRC"
  else
    git -C "$LLAMA_SRC" fetch --depth 1 origin master
    git -C "$LLAMA_SRC" checkout --detach FETCH_HEAD
  fi

  cmake -S "$LLAMA_SRC" -B "$LLAMA_SRC/build" -DLLAMA_CURL=OFF -DGGML_OPENMP=OFF -DCMAKE_BUILD_TYPE=Release
  cmake --build "$LLAMA_SRC/build" --config Release -j "${SELMA0_BUILD_JOBS_V1:-2}" --target llama-server
  [ -x "$SERVER_BIN" ] || fail "llama-server build completed but executable was not found at $SERVER_BIN"
  printf 'runtime=%s\n' "$SERVER_BIN"
}

is_running() {
  [ -f "$PID_FILE" ] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

start_server() {
  is_running && { printf 'already_running pid=%s\n' "$(cat "$PID_FILE")"; return; }
  [ -x "$SERVER_BIN" ] || fail "llama-server not found. Run: $0 install-runtime"

  local model ctx
  model="$(select_model)"
  ctx="$(profile_ctx)"
  printf '%s\n' "$model" > "$MODEL_FILE_STATE"

  nohup "$SERVER_BIN" \
    --host "$HOST" \
    --port "$PORT" \
    --model "$model" \
    --ctx-size "$ctx" \
    --n-gpu-layers 0 \
    >"$LOG_FILE" 2>&1 &
  printf '%s\n' "$!" > "$PID_FILE"
  sleep 1
  is_running || { rm -f "$PID_FILE"; fail "llama-server exited during startup. See $LOG_FILE"; }
  printf 'started pid=%s endpoint=http://%s:%s/v1 model=%s ctx=%s\n' "$(cat "$PID_FILE")" "$HOST" "$PORT" "$model" "$ctx"
}

stop_server() {
  if ! is_running; then
    rm -f "$PID_FILE"
    printf 'stopped\n'
    return
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  printf 'stopped\n'
}

status_server() {
  if is_running; then
    printf 'status=running\n'
    printf 'pid=%s\n' "$(cat "$PID_FILE")"
    printf 'endpoint=http://%s:%s/v1\n' "$HOST" "$PORT"
    [ -f "$MODEL_FILE_STATE" ] && printf 'model=%s\n' "$(cat "$MODEL_FILE_STATE")"
  else
    printf 'status=stopped\n'
    return 1
  fi
}

usage() {
  cat <<EOF
Usage: $0 {install-runtime|profile|start|stop|status}

Environment overrides:
  SELMA0_MODEL_V1             Explicit GGUF model path
  SELMA0_MODEL_DIR_V1         GGUF directory (default: $MODEL_DIR)
  SELMA0_LLAMA_SERVER_V1      Existing llama-server executable
  SELMA0_LLAMA_SRC_V1         llama.cpp source checkout
  SELMA0_BUILD_JOBS_V1        Build parallelism (default: 2)
EOF
}

case "${1:-}" in
  install-runtime) install_runtime ;;
  profile) profile ;;
  start) start_server ;;
  stop) stop_server ;;
  status) status_server ;;
  *) usage; exit 2 ;;
esac
