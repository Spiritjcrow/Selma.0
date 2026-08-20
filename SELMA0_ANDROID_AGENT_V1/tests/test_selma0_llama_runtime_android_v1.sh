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
#!/usr/bin/env bash
trap 'exit 0' TERM INT
while :; do sleep 1; done
EOF
chmod +x "$TMP/fake-llama-server"

export SELMA0_BASE_V1="$TMP/base"
export SELMA0_LLAMA_STATE_DIR_V1="$TMP/state"
export SELMA0_MODEL_DIR_V1="$TMP/base/models"
export SELMA0_MODEL_V1="$TMP/base/models/test.gguf"
export SELMA0_LLAMA_SERVER_V1="$TMP/fake-llama-server"

PROFILE="$($MANAGER profile)"
grep -q '^context_tokens=' <<<"$PROFILE"
grep -q "^model=$SELMA0_MODEL_V1$" <<<"$PROFILE"

START="$($MANAGER start)"
grep -q '^started pid=' <<<"$START"
$MANAGER status | grep -q '^status=running$'
$MANAGER stop | grep -q '^stopped$'
if $MANAGER status >/dev/null 2>&1; then
  echo 'expected stopped status to return nonzero' >&2
  exit 1
fi

echo 'SELMA0_LLAMA_RUNTIME_SMOKE_OK'
