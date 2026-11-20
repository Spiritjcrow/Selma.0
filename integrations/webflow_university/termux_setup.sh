#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
pkg install -y python
python -m pip install -r requirements.txt
python preflight.py
mkdir -p "$HOME/.config/selma"
TOKEN_FILE="$HOME/.config/selma/webflow_university_token"
if [ ! -s "$TOKEN_FILE" ]; then
  (umask 077; python -c 'import secrets;print(secrets.token_urlsafe(48))' > "$TOKEN_FILE")
fi
chmod 600 "$TOKEN_FILE"
printf '\nPreflight complete. Start HTTP bridge with:\n'
printf 'CONNECTOR_MODE=http CONNECTOR_BEARER_TOKEN="$(cat "$HOME/.config/selma/webflow_university_token")" python webflow_university_connector.py\n'
