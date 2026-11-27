#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_RUNTIME="$REPO_ROOT/SELMA0_ANDROID_AGENT_V1"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_ROOT="$DATA_HOME/selmaos"
BIN_ROOT="$HOME/.local/bin"
APP_ROOT="$DATA_HOME/applications"
SERVICE_ROOT="$CONFIG_HOME/systemd/user"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
command -v xdg-open >/dev/null 2>&1 || { echo "xdg-open is required" >&2; exit 1; }
test -f "$SOURCE_RUNTIME/selma0_runtime_command_core_android_v1.py"

mkdir -p "$DATA_ROOT" "$BIN_ROOT" "$APP_ROOT" "$SERVICE_ROOT"
STAGE="$(mktemp -d "$DATA_ROOT/.install.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/runtime"
cp -R "$SOURCE_RUNTIME/." "$STAGE/runtime/"

rm -rf "$DATA_ROOT/runtime.previous"
if [ -d "$DATA_ROOT/runtime" ]; then
  mv "$DATA_ROOT/runtime" "$DATA_ROOT/runtime.previous"
fi
mv "$STAGE/runtime" "$DATA_ROOT/runtime"

install -m 0755 "$SCRIPT_DIR/selmaos-runtime" "$BIN_ROOT/selmaos-runtime"
install -m 0755 "$SCRIPT_DIR/selmaos-open" "$BIN_ROOT/selmaos-open"

cat > "$APP_ROOT/selmaos.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SelmaOS
Comment=Open the local SelmaOS workspace
Exec=$BIN_ROOT/selmaos-open
Terminal=false
Categories=Utility;Development;
EOF

cat > "$SERVICE_ROOT/selmaos.service" <<EOF
[Unit]
Description=SelmaOS loopback runtime
After=default.target

[Service]
Type=simple
ExecStart=$BIN_ROOT/selmaos-runtime
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

if [ "${1:-}" = "--enable-service" ]; then
  command -v systemctl >/dev/null 2>&1 || { echo "systemctl is required for --enable-service" >&2; exit 1; }
  systemctl --user daemon-reload
  systemctl --user enable --now selmaos.service
fi

echo "SelmaOS installed. Run: $BIN_ROOT/selmaos-open"
