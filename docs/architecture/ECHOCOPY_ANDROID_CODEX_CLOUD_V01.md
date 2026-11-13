# Selma° EchoCopy — Android + Codex Cloud workstation

## Implemented
`tools/echocopy_worker.py` is a **read-only, opt-in Python worker** that checks the head of [PR #50](https://github.com/Spiritjcrow/Selma.0/pull/50) through an already authenticated `gh` CLI. It maintains a capped 500-entry SQLite event ledger in an application-private directory, exports optional JSON snapshots, and supports `run`, `once`, `status`, `stop`, and `resume` commands.

It does **not** create a distinct GitHub account, provide LLM inference, run Android APK acceptance, repair CI, alter PRs, commit code, or grant unattended permissions. It is a deterministic virtual *monitoring worker*, not an independent White tester. Android may stop a background Termux process.

## Android Termux (no root; no SD executable required)

Prerequisites: Android Termux with Python 3.11+, `git` and `gh`, plus owner-authorized GitHub login via `gh auth login`. Put executable Python in Termux internal private storage and JSON reports on removable SD. The user has previously created `~/SelmaSD`.

On this feature branch, retrieve and integrity-check the worker:

```bash
set -euo pipefail
BR='feature%2Fechocopy-android-codex-cloud-20261113'
TARGET="$HOME/.selma/echocopy/worker.py"
mkdir -p "$(dirname "$TARGET")"
gh api "repos/Spiritjcrow/Selma.0/contents/tools/echocopy_worker.py?ref=$BR" --jq '.content' | tr -d '\n' | base64 -d > "$TARGET"
python3 -m py_compile "$TARGET"
python3 "$TARGET" once --report "$HOME/SelmaSD/reports/echocopy_status.json"
```

To start a local background worker after reviewing the actual code:

```bash
nohup python3 -u "$HOME/.selma/echocopy/worker.py" run --interval 300 --report "$HOME/SelmaSD/reports/echocopy_status.json" > "$HOME/.selma/echocopy/run.log" 2>&1 < /dev/null &
```

Status and stop:

```bash
python3 ~/.selma/echocopy/worker.py status
python3 ~/.selma/echocopy/worker.py stop
```

To restart after stopping:

```bash
python3 ~/.selma/echocopy/worker.py resume
```
Then launch `run` again.

## PC-like workstation without PC emulation

In Android Chrome, enable **Desktop site**, then:
1. Open https://github.com/codespaces and launch a Codespace on **this feature branch**. A Codespace is a cloud Linux PC with a terminal and browser-based VS Code; personal GitHub accounts have bounded included use.
2. Sign in to https://chatgpt.com/codex. On the web create/publish a Codex Cloud environment for this GitHub repository (when access is available). On mobile, choose the published environment.
3. Give Codex an explicit scoped task: inspect this worker and its tests, run `python3 -m unittest discover -s tests -p 'test_echocopy_worker.py' -v`, and propose limited changes on a feature branch. Do not claim independent White/device or APK CI approval.

Codex Cloud and GitHub Codespaces are separate cloud computers; a process in one does not automatically run in the other. Codespaces may auto-stop at idle, and Codex Cloud tasks are not perpetual daemons. Neither requires the Android device to act as a literal x86 PC.

## Safety and evidence classification
- All PR access uses the user's existing `gh` login; no token copy, fake credentials, or new permissions.
- Hard-coded GET-only read of PR #50 head SHA; no general command executor, shell interpolation, or arbitrary task execution.
- State in `~/.selma/echocopy/events.sqlite3`; optional SD report contains commit/status only.
- Fail closed on offline GitHub, invalid SHA, changed PR head, missing `gh`.
- Stop via the `STOP` file; the worker checks once each second between polls.
- `UNVERIFIED` statuses are never silently promoted by the monitor.

## Verified local tests
The five stdlib test cases in `tests/test_echocopy_worker.py` were run locally during preparation, 5/5 PASS; Android execution and cloud environment provisioning remain pending. No background process has been started remotely by this change.
