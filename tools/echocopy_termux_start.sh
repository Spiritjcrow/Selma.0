#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

STATE="$HOME/.selma/echocopy"
DEST="$STATE/worker.py"
REPORT="$HOME/SelmaSD/reports/echocopy_status.json"
EXPECTED_BLOB="4c130dc7f296647184553937fe0fc245bf5d10f2"
BRANCH='feature%2Fechocopy-android-codex-cloud-20261113'

for cmd in gh git python3 base64; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED: missing $cmd"; exit 2; }
done
[ -d "$HOME/SelmaSD" ] || { echo "BLOCKED: missing SelmaSD workspace"; exit 2; }
gh auth status -h github.com >/dev/null 2>&1 || { echo "BLOCKED: GitHub CLI login required"; exit 2; }
mkdir -p "$STATE" "$HOME/SelmaSD/reports"
[ ! -e "$STATE/STOP" ] || { echo "STOP switch set; use 'python3 $DEST resume' before starting"; exit 2; }
TMP="$(mktemp "$STATE/echocopy.XXXXXXXX")"
trap 'rm -f "$TMP"' EXIT

gh api "repos/Spiritjcrow/Selma.0/contents/tools/echocopy_worker.py?ref=$BRANCH" --jq '.content' \
  | tr -d '\n' | base64 -d > "$TMP"
ACTUAL_BLOB="$(git hash-object "$TMP")"
[ "$ACTUAL_BLOB" = "$EXPECTED_BLOB" ] || { echo "BLOCKED: GitHub source mismatch: $ACTUAL_BLOB"; exit 2; }
python3 -m py_compile "$TMP"
cp "$TMP" "$DEST"
chmod 600 "$DEST"

nohup python3 -u "$DEST" run --interval 300 --report "$REPORT" \
  >> "$STATE/run.log" 2>&1 < /dev/null &
sleep 2

echo '=== ECHOCOPY STATUS ==='
python3 "$DEST" status
printf 'Log: %s\nSD status: %s\n' "$STATE/run.log" "$REPORT"
tail -n 3 "$STATE/run.log"
