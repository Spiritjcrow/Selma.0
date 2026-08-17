#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${SELMA0_SMOKE_PORT_V1:-18765}"
TMP_ROOT="${TMPDIR:-$ROOT}/selma0_smoke_${$}"
LOG_PATH="$TMP_ROOT/runtime.log"
PID=""

mkdir -p "$TMP_ROOT"

cleanup() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT INT TERM

cd "$ROOT"
export SELMA0_BASE_V1="$TMP_ROOT/runtime"
export SELMA0_HOST_V1="127.0.0.1"
export SELMA0_PORT_V1="$PORT"

printf '%s\n' '[1/4] Compiling Selma Android agent sources...'
python -m compileall -q .

printf '%s\n' '[2/4] Running command-core/device/CrowRF unit tests...'
python -m unittest discover -s tests -p 'test_*.py' -v

printf '%s\n' '[3/4] Starting isolated stacked device/CrowRF runtime...'
python selma0_runtime_device_crowrf_android_v1.py >"$LOG_PATH" 2>&1 &
PID="$!"

printf '%s\n' '[4/4] Probing runtime status and registered tools without executing device effects...'
python - <<'PY'
import json
import os
import time
import urllib.request

port = int(os.environ["SELMA0_PORT_V1"])
base = f"http://127.0.0.1:{port}"
last_error = None

for _ in range(30):
    try:
        with urllib.request.urlopen(base + "/api/selma0/status/v1", timeout=1.0) as response:
            status = json.load(response)
        break
    except Exception as exc:
        last_error = exc
        time.sleep(0.2)
else:
    raise SystemExit(f"runtime did not become ready: {last_error}")

with urllib.request.urlopen(base + "/api/selma0/tools/v1", timeout=2.0) as response:
    tools_status = json.load(response)

tools = tools_status.get("tools", [])
names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
required = {
    "selma.status",
    "replika.preview_archive",
    "replika.import_archive",
    "device.battery_status",
    "device.wifi_connection",
    "device.location",
    "device.notify",
    "device.vibrate",
    "crowrf.wifi_scan",
    "crowrf.session_start",
    "crowrf.capture_wifi_scan",
    "crowrf.session_status",
    "crowrf.session_recent",
    "crowrf.session_verify",
    "crowrf.derive_rssi_summary",
}
missing = sorted(required - names)

if status.get("name") != "Selma.0":
    raise SystemExit(f"unexpected runtime identity: {status.get('name')!r}")
if "command_core" not in status:
    raise SystemExit("command_core status is missing")
if missing:
    raise SystemExit(f"required tools are missing: {missing}")

print(json.dumps({
    "ok": True,
    "runtime": status.get("runtime"),
    "registered_tool_count": len(names),
    "required_tools_present": sorted(required),
    "memory_db": status.get("memory_db"),
    "device_effects_executed": False,
    "sensitive_scans_executed": False,
}, indent=2))
PY

printf '%s\n' 'Selma.0 stacked command-core/device/CrowRF smoke test PASSED.'
