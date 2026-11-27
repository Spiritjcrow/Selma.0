#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
state="$HOME/.local/share/selma-lunar"
colors="$HOME/.termux/colors.properties"
rc="$HOME/.bashrc"
hook='[ ! -r "$HOME/.local/share/selma-lunar/lunar.bash" ] || . "$HOME/.local/share/selma-lunar/lunar.bash"'
mkdir -p "$state" "$HOME/.termux"
if [[ "${1:-install}" == remove ]]; then
  if [[ -f "$state/palette" && -f "$colors" ]] && cmp -s "$state/palette" "$colors"; then
    if [[ -f "$state/original" ]]; then cp "$state/original" "$colors"; else rm "$colors"; fi
  fi
  if [[ -f "$rc" ]]; then awk -v hook="$hook" '$0!=hook' "$rc" > "$state/rc.tmp"; cat "$state/rc.tmp" > "$rc"; fi
  rm -f "$state/lunar.bash" "$state/palette" "$state/original"
else
  if [[ ! -f "$state/palette" && -f "$colors" ]]; then cp "$colors" "$state/original"; fi
  cp colors.properties "$state/palette"; cp "$state/palette" "$colors"; cp lunar.bash "$state/lunar.bash"
  touch "$rc"; grep -Fxq "$hook" "$rc" || printf '\n%s\n' "$hook" >> "$rc"
  cp theme.sh "$state/theme.sh"
fi
if command -v termux-reload-settings >/dev/null; then termux-reload-settings; fi
