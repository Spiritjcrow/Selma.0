#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SELMA0_HOME_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
mkdir -p "$SELMA0_HOME_V1"

pkg update -y
pkg install -y python git

cp -f "$(dirname "$0")/selma0_runtime_android_v1.py" "$SELMA0_HOME_V1/selma0_runtime_android_v1.py"
cp -f "$(dirname "$0")/selma0_llm_router_android_v1.py" "$SELMA0_HOME_V1/selma0_llm_router_android_v1.py"
cp -f "$(dirname "$0")/selma0_memory_android_v1.py" "$SELMA0_HOME_V1/selma0_memory_android_v1.py"

cat > "$SELMA0_HOME_V1/selma0_start_android_v1.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$HOME/SELMA0_ANDROID_AGENT_V1"
export SELMA0_BASE_V1="$HOME/SELMA0_ANDROID_AGENT_V1"
exec python selma0_runtime_android_v1.py
EOF
chmod +x "$SELMA0_HOME_V1/selma0_start_android_v1.sh"

echo "Selma.0 Android Agent V1 installed at: $SELMA0_HOME_V1"
echo "Start: $SELMA0_HOME_V1/selma0_start_android_v1.sh"
echo "UI: http://127.0.0.1:8765"
echo "Offline LLM default endpoint: http://127.0.0.1:8080/v1"
