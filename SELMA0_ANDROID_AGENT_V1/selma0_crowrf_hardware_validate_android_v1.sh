#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

if [ "${1:-}" != "--confirmed-sensitive-scan" ]; then
  cat <<'EOF'
Usage: selma0_crowrf_hardware_validate_android_v1.sh --confirmed-sensitive-scan

This validation performs exactly one real Wi-Fi scan through Termux:API.
Nearby SSID/BSSID data is treated as sensitive location-context data.
The validation database is temporary, network identities are not printed,
and the temporary database is erased on exit.
EOF
  exit 2
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
TMP_ROOT="${TMPDIR:-$ROOT}/selma0_crowrf_hw_${$}"
DB_PATH="$TMP_ROOT/crowrf_hw.sqlite3"
mkdir -p "$TMP_ROOT"

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT INT TERM

cd "$ROOT"

if ! command -v termux-wifi-scaninfo >/dev/null 2>&1; then
  echo "ERROR: termux-wifi-scaninfo is unavailable. Install the Termux:API app and termux-api package." >&2
  exit 3
fi

export SELMA0_CROWRF_HW_DB_V1="$DB_PATH"

python - <<'PY'
import json
import os

from selma0_crowrf_derived_metrics_android_v1 import derive_rssi_summary_v1
from selma0_crowrf_measurement_store_android_v1 import Selma0CrowRFMeasurementStoreAndroidV1
from selma0_device_bridge_android_v1 import Selma0TermuxDeviceBridgeAndroidV1

store = Selma0CrowRFMeasurementStoreAndroidV1(
    db_path=os.environ["SELMA0_CROWRF_HW_DB_V1"]
)
bridge = Selma0TermuxDeviceBridgeAndroidV1()
session = store.start_session(
    label="hardware-validation",
    metadata={"purpose": "single-scan hardware validation", "temporary": True},
)
captured = store.capture_wifi_scan(session_id=session["session_id"], bridge=bridge)
verified = store.verify_session(session["session_id"])
if not verified.get("ok"):
    raise SystemExit(f"measurement chain verification failed: {verified}")

scan = captured.get("scan") or {}
if scan.get("measurement_kind") != "measured":
    raise SystemExit("hardware scan was not labeled measured")
if scan.get("inference") is not None:
    raise SystemExit("hardware scan unexpectedly contains inference")

derived = derive_rssi_summary_v1(store, session["session_id"])
claims = derived.get("claims") or {}
if any(claims.get(name) for name in ("distance", "geometry", "csi", "occupancy")):
    raise SystemExit(f"derived hardware validation made an unsupported physical claim: {claims}")

print(json.dumps({
    "ok": True,
    "measurement_kind": scan.get("measurement_kind"),
    "source": scan.get("source"),
    "record_count": scan.get("record_count"),
    "event_hash": captured.get("event_hash"),
    "chain_verified": True,
    "derived_network_count": derived.get("network_count"),
    "derived_claims": claims,
    "network_identities_printed": False,
    "temporary_database": True,
}, indent=2))
PY

echo "CrowRF hardware validation PASSED. Temporary scan database erased on exit."
