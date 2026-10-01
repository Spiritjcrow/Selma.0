#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SELMA0_HOME_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SOURCE_DIR/.." && pwd)"
mkdir -p "$SELMA0_HOME_V1"

pkg update -y
pkg install -y python python-cryptography git cmake make termux-api

for file in \
  selma0_runtime_android_v1.py \
  selma0_runtime_command_core_android_v1.py \
  selma0_runtime_device_crowrf_android_v1.py \
  selma0_llm_router_android_v1.py \
  selma0_llama_runtime_android_v1.sh \
  selma0_avatar_presence_android_v1.py \
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
  selma0_crowrf_hardware_validate_android_v1.sh
do
  cp -f "$SOURCE_DIR/$file" "$SELMA0_HOME_V1/$file"
done
chmod +x "$SELMA0_HOME_V1/selma0_llama_runtime_android_v1.sh"
chmod +x "$SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"
chmod +x "$SELMA0_HOME_V1/selma0_crowrf_hardware_validate_android_v1.sh"

rm -rf "$SELMA0_HOME_V1/core"
cp -R "$REPO_ROOT/core" "$SELMA0_HOME_V1/core"

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
echo "Validate software stack: $SELMA0_HOME_V1/selma0_smoke_test_android_v1.sh"
echo "Validate llama runtime manager: bash $SELMA0_HOME_V1/tests/test_selma0_llama_runtime_android_v1.sh"
echo "Install/build llama.cpp server: $SELMA0_HOME_V1/selma0_llama_runtime_android_v1.sh install-runtime"
echo "Start local LLM: $SELMA0_HOME_V1/selma0_llama_runtime_android_v1.sh start"
echo "Adult Mode status: python $SELMA0_HOME_V1/selma0_avatar_presence_android_v1.py status"
echo "Install signed Adult Mode pack: python $SELMA0_HOME_V1/selma0_avatar_presence_android_v1.py install /path/to/pack.zip --trust-on-first-use"
echo "Validate one real CrowRF scan: $SELMA0_HOME_V1/selma0_crowrf_hardware_validate_android_v1.sh --confirmed-sensitive-scan"
echo "Start: $SELMA0_HOME_V1/selma0_start_android_v1.sh"
echo "UI: http://127.0.0.1:8765"
echo "Adult Mode UI: http://127.0.0.1:8765/adult-mode"
echo "Tools: http://127.0.0.1:8765/api/selma0/tools/v1"
echo "Offline LLM default endpoint: http://127.0.0.1:8080/v1"
echo "Command Core, rootless Termux device bridge, managed local llama.cpp runtime, verified Adult Mode sprite presence, measured CrowRF acquisition, local audit, tests, and Safety Guardian deployed."
echo "GGUF weights and the final photorealistic 3D rig are intentionally not bundled; local paths are verified rather than fabricated."
echo "Termux:API Android companion app permissions are still required for Wi-Fi scan, location, notification, vibration, and SMS capabilities."
