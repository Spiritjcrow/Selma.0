#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANAGER="$ROOT/selma0_llama_runtime_android_v1.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

bash -n "$MANAGER"
mkdir -p "$TMP/base/models" "$TMP/state"
printf 'GGUF' > "$TMP/base/models/test.gguf"

cat > "$TMP/fake-llama-server" <<'EOF'
#!/usr/bin/env python3
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
port = 8080
for i, arg in enumerate(sys.argv[:-1]):
    if arg == "--port": port = int(sys.argv[i + 1])
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404); self.end_headers(); return
        body = json.dumps({"status": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass
ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
EOF
chmod +x "$TMP/fake-llama-server"

export SELMA0_BASE_V1="$TMP/base"
export SELMA0_LLAMA_STATE_DIR_V1="$TMP/state"
export SELMA0_MODEL_DIR_V1="$TMP/base/models"
export SELMA0_MODEL_V1="$TMP/base/models/test.gguf"
export SELMA0_LLAMA_SERVER_V1="$TMP/fake-llama-server"
export SELMA0_LLAMA_PORT_V1="18080"
export SELMA0_LLAMA_READY_ATTEMPTS_V1="5"

PROFILE="$(bash "$MANAGER" profile)"
grep -q '^context_tokens=' <<<"$PROFILE"
grep -q "^model=$SELMA0_MODEL_V1$" <<<"$PROFILE"

START="$(bash "$MANAGER" start)"
grep -q '^started pid=' <<<"$START"
STATUS="$(bash "$MANAGER" status)"
grep -q '^status=running$' <<<"$STATUS"
STOP="$(bash "$MANAGER" stop)"
grep -q '^stopped$' <<<"$STOP"
if bash "$MANAGER" status >/dev/null 2>&1; then
  echo 'expected stopped status to return nonzero' >&2
  exit 1
fi

cat > "$TMP/fake-no-health" <<'EOF'
#!/usr/bin/env bash
trap 'exit 0' TERM INT
while :; do sleep 1; done
EOF
chmod +x "$TMP/fake-no-health"
export SELMA0_LLAMA_SERVER_V1="$TMP/fake-no-health"
export SELMA0_LLAMA_READY_ATTEMPTS_V1="2"
if bash "$MANAGER" start >/dev/null 2>&1; then
  echo 'expected PID-only server to fail readiness' >&2
  bash "$MANAGER" stop >/dev/null 2>&1 || true
  exit 1
fi

echo 'SELMA0_LLAMA_RUNTIME_SMOKE_OK'
