#!/data/data/com.termux/files/usr/bin/bash
# Optional local OmniRoute gateway for Selma.0. No credentials are persisted.
set -euo pipefail

readonly OMNI_HOST='127.0.0.1'
readonly OMNI_PORT='20128'
readonly OMNI_BASE="http://${OMNI_HOST}:${OMNI_PORT}/v1"
readonly SELMA_HOME="$HOME/SELMA0_ANDROID_AGENT_V1"

die() { printf 'Selma.0 OmniRoute: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

check_termux() {
  case "${PREFIX:-}" in
    /data/data/com.termux/files/usr|/data/data/com.termux/files/usr/*) ;;
    *) die 'Install must be run inside the Termux app on Android.' ;;
  esac
  need pkg
}

check_node() {
  node -e '
    const a = process.versions.node.split(".").map(Number);
    const [major, minor, patch] = a;
    const allowed = (major === 22 && (minor > 22 || (minor === 22 && patch >= 2))) ||
                    (major >= 24 && major < 27);
    if (!allowed) { console.error("Unsupported Node.js " + process.version + "; install Node 22.22.2+ or 24–26."); process.exit(1); }
  ' || die 'Node version is unsupported by current OmniRoute releases.'
}

check_gateway() {
  need python
  python - <<'PY'
import sys
import urllib.error
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:20128/', timeout=3) as response:
        print('OmniRoute reachable on loopback: HTTP', response.status)
except (urllib.error.URLError, TimeoutError, OSError) as error:
    print('OmniRoute is not reachable locally:', error, file=sys.stderr)
    sys.exit(1)
PY
}

case "${1:-help}" in
  install)
    check_termux
    pkg update -y
    pkg install -y nodejs python build-essential git
    need node
    check_node
    need npm
    npm install -g omniroute
    need omniroute
    printf 'OmniRoute installed. Start with: %s start\n' "$0"
    ;;
  start)
    need omniroute
    # Loopback-only: do not expose provider credentials or dashboard to LAN.
    export HOST="$OMNI_HOST" HOSTNAME="$OMNI_HOST" PORT="$OMNI_PORT"
    exec omniroute
    ;;
  status)
    check_gateway
    ;;
  run-selma)
    check_gateway >/dev/null || die 'Start OmniRoute first in another Termux session.'
    [ -n "${OMNIROUTE_API_KEY:-}" ] || die 'Export your endpoint key as OMNIROUTE_API_KEY in this session.'
    [ -x "$SELMA_HOME/selma0_start_android_v1.sh" ] || die 'Install the Selma.0 Android Agent first.'
    export SELMA0_ONLINE_BASE_URL_V1="$OMNI_BASE"
    export SELMA0_ONLINE_API_KEY_V1="$OMNIROUTE_API_KEY"
    # Explicit subscription-quota routing avoids unexpected per-token bills;
    # an operator can override with an audited free-only combo model id.
    export SELMA0_ONLINE_MODEL_V1="${SELMA0_OMNIROUTE_MODEL_V1:-auto/subscription}"
    exec "$SELMA_HOME/selma0_start_android_v1.sh"
    ;;
  codex-preview)
    check_gateway >/dev/null || die 'Start OmniRoute first.'
    need omniroute
    need codex
    omniroute setup-codex --dry-run
    ;;
  codex)
    check_gateway >/dev/null || die 'Start OmniRoute first.'
    need omniroute
    need codex
    [ -n "${OMNIROUTE_API_KEY:-}" ] || die 'Export the OmniRoute endpoint key as OMNIROUTE_API_KEY.'
    shift
    exec omniroute run codex --model "${SELMA0_OMNIROUTE_MODEL_V1:-auto/subscription}" -- "$@"
    ;;
  help|-h|--help)
    cat <<'HELP'
Usage: selma0_omniroute_termux_android_v1.sh COMMAND
  install         Install verified prerequisites and OmniRoute in Termux
  start           Run the gateway on 127.0.0.1:20128 (foreground)
  status          Check local gateway reachability
  run-selma       Start existing Selma Agent with OPTIONAL OmniRoute fallback
  codex-preview   Preview Codex CLI integration without changing config
  codex [ARGS]    Run locally installed Codex CLI via OmniRoute

Dashboard: http://127.0.0.1:20128
First connect permitted providers, then create an endpoint API key.
In a new Termux session: export OMNIROUTE_API_KEY='<endpoint key>'
The default model 'auto/subscription' fails closed to billable fallbacks.
Private prompts sent to online providers will leave the device.
No device installation or provider connection is performed by this help command.
HELP
    ;;
  *) die "Unknown command '$1'. Use 'help'." ;;
esac
