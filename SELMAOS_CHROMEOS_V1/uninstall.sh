#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now selmaos.service >/dev/null 2>&1 || true
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

rm -f "$HOME/.local/bin/selmaos-runtime"
rm -f "$HOME/.local/bin/selmaos-open"
rm -f "$DATA_HOME/applications/selmaos.desktop"
rm -f "$CONFIG_HOME/systemd/user/selmaos.service"

if [ "${1:-}" = "--purge-data" ]; then
  rm -rf "$DATA_HOME/selmaos"
else
  rm -rf "$DATA_HOME/selmaos/runtime" "$DATA_HOME/selmaos/runtime.previous"
fi

echo "SelmaOS runtime removed. Use --purge-data to remove local state."
