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
  selma0_crowrf_derived_metrics_android_v1.py \
  selma0_smoke_test_android_v1.sh \
  selma0_crowrf_hardware_validate_android_v1.sh \
  selma0_first_run_android_v1.py
do
  cp -f "$SOURCE_DIR/$file" "$SELMA0_HOME_V1/$file"
done
chmod +x "$SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"
chmod +x "$SELMA0_HOME_V1/selma0_crowrf_hardware_validate_android_v1.sh"

mkdir -p "$SELMA0_HOME_V1/tests"
if [ -d "$SOURCE_DIR/tests" ]; then
  cp -R "$SOURCE_DIR/tests/." "$SELMA0_HOME_V1/tests/"
fi

mkdir -p "$SELMA0_HOME_V1/skills"
rm -rf "$SELMA0_HOME_V1/skills/replika_migration_v1"
cp -R "$SOURCE_DIR/skills/replika_migration_v1" "$SELMA0_HOME_V1/skills/replika_migration_v1"

cat > "$SELMA0_HOME_V1/selma0_start_android_v1.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$HOME/SELMA0_ANDROID_AGENT_V1"
export SELMA0_BASE_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
if [ ! -f "$SELMA0_BASE_V1/selma0_setup_v1.json" ]; then
  echo "SelmaOS first-run wizard: http://127.0.0.1:8766"
  if command -v termux-open-url >/dev/null 2>&1; then
    (sleep 1; termux-open-url http://127.0.0.1:8766 >/dev/null 2>&1) &
  fi
  exec python selma0_first_run_android_v1.py
fi
exec python selma0_runtime_device_crowrf_android_v1.py
EOF
chmod +x "$SELMA0_HOME_V1/selma0_start_android_v1.sh"

echo "Selma.0 Android Agent V1 installed at: $SELMA0_HOME_V1"
echo "Run checks: $SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"
echo "Start: $SELMA0_HOME_V1/selma0_start_android_v1.sh"
echo "First launch: http://127.0.0.1:8766; subsequent runs: http://127.0.0.1:8765"
echo "Offline model endpoint: http://127.0.0.1:8080/v1 (model/runtime not installed automatically)"
echo "Termux:API companion and explicit Android permission enrollment are required for device effects."
