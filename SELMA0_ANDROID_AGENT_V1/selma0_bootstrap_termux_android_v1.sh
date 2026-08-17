#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SELMA0_HOME_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$SELMA0_HOME_V1"

pkg update -y
pkg install -y python git termux-api

for file in \
  selma0_runtime_android_v1.py \
  selma0_runtime_command_core_android_v1.py \
  selma0_runtime_device_crowrf_android_v1.py \
  selma0_llm_router_android_v1.py \
  selma0_memory_android_v1.py \
  selma0_safety_guardian_android_v1.py \
  selma0_audit_log_android_v1.py \
  selma0_command_router_android_v1.py \
  selma0_permission_engine_android_v1.py \
  selma0_tool_registry_android_v1.py \
  selma0_device_bridge_android_v1.py \
  selma0_crowrf_wifi_scan_android_v1.py \
  selma0_crowrf_measurement_store_android_v1.py \
  selma0_smoke_test_android_v1.sh
do
  cp -f "$SOURCE_DIR/$file" "$SELMA0_HOME_V1/$file"
done
chmod +x "$SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"

mkdir -p "$SELMA0_HOME_V1/tests"
if [ -d "$SOURCE_DIR/tests" ]; then
  cp -R "$SOURCE_DIR/tests/." "$SELMA0_HOME_V1/tests/"
fi

mkdir -p "$SELMA0_HOME_V1/skills"
rm -rf "$SELMA0_HOME_V1/skills/replika_migration_v1"
cp -R "$SOURCE_DIR/skills/replika_migration_v1" "$SELMA0_HOME_V1/skills/replika_migration_v1"

cat > "$SELMA0_HOME_V1/selma0_start_android_v1.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$HOME/SELMA0_ANDROID_AGENT_V1"
export SELMA0_BASE_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
exec python selma0_runtime_device_crowrf_android_v1.py
EOF
chmod +x "$SELMA0_HOME_V1/selma0_start_android_v1.sh"

echo "Selma.0 Android Agent V1 installed at: $SELMA0_HOME_V1"
echo "Validate: $SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"
echo "Start: $SELMA0_HOME_V1/selma0_start_android_v1.sh"
echo "UI: http://127.0.0.1:8765"
echo "Tools: http://127.0.0.1:8765/api/selma0/tools/v1"
echo "Offline LLM default endpoint: http://127.0.0.1:8080/v1"
echo "Command Core, rootless Termux device bridge, measured CrowRF Wi-Fi acquisition, append-only CrowRF session storage, local audit, Replika migration, tests, smoke validation, and Safety Guardian deployed."
echo "Termux:API Android companion app permissions are still required for Wi-Fi scan, location, notification, vibration, and SMS capabilities."
