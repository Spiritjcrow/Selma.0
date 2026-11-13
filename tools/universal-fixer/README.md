# Selma° Universal Fixer v0.3 — real repair worker with local A/B/C/D approval UI

An **executable** cross-platform recovery workbench: real GitHub inventory, source-backed SQLite audit/decisions, searchable Android-friendly HTML report, a bounded **actual Git repair executor**, and an **authenticated local browser A/B/C/D approval UI**. No fake remote CI, Android, or deployment status.

## Install

Python **3.10+** and Git (Windows 11, Linux, macOS, ChromeOS Linux, Android Termux with Git/Python). Standard library only; no root or paid API needed for the local runner. GitHub inventory of private repositories requires appropriately scoped `GITHUB_TOKEN`, stored in environment only, never in source/reports. The ChatGPT GitHub connector credential is not exported to your terminal.

```sh
python -m unittest discover -s tests -v
python -m fixer --db ./local.sqlite3 sync --repos config/repositories.json
python -m fixer --db ./local.sqlite3 report --output output
python -m fixer --db ./local.sqlite3 queue
python -m fixer --db ./local.sqlite3 decide 'Spiritjcrow/Selma.0:issue:43' C
python -m fixer --db ./local.sqlite3 audit
```

Inventory flags are A=approve **read-only review**, B=hold, C=request evidence, D=reject. These existing choices **do not authorize commits**.

## Actual repair on a clean, owned Git checkout

Use a current, reviewed patch JSON (`docs/FIXER_ARCHITECTURE_AND_COMPLETION.md` gives the strict schema) stored **outside the checkout**. If the tests already pass, **no repair commit** is made; if they fail after patch, **no commit** is made. A path or SHA mismatch blocks the action.

```sh
python -m fixer repair-plan --repo /absolute/path/to/owned/repo --plan /safe/plan.json
# Read and explicitly approve the exact 64-hex plan_sha256 from this command.
python -m fixer repair-run --repo /absolute/path/to/owned/repo --plan /safe/plan.json --approve-digest 64_HEX_FROM_PLAN --evidence /safe/repair-001.json
```

The executor creates a disposable worktree, runs **real pre-fix failing unit tests**, applies one exact, approved, source-hash-bound text patch, reruns the checks, creates **one new `fixer/` branch and a Git commit** if green, and emits provenance JSON. Existing `main` is not modified. No push, merge, bill, wallet transaction, deployment, secrets import, system setting modification, or external cloud action is performed. Local test commands can execute repository-supplied code: only use trusted/owned workspaces; production needs container/VM isolation.

## One-click local approval (Android browser/desktop)

On the device hosting the checked-out source (Windows/Linux/macOS or Android Termux), start the loopback-only approval server. It prints a **fresh one-session private token**. Open the local address in the same device's browser, enter the token once, then review the exact patch and choose A/B/C/D. A **runs real red/green tests and commits an isolated branch**. B holds, C requests evidence, D rejects; those alternatives never run source code or post external actions.

```sh
python -m fixer serve --repo /path/to/owned/clean/checkout \
  --plan /safe/reviewed-plan.json --evidence /safe/repair-001.json --port 8768
# Open http://127.0.0.1:8768/ in the same device browser.
```

This is a **local** UI, not a remotely hosted service or Google OAuth login. A valid one-session bearer token and exact same-origin browser request are required for actions. It does not expose a command shell, use cookies, or write credentials to disk. Stop it with Ctrl+C. Never expose this port to a public network. Tests for real loopback HTTP approval and actual Git commit pass locally; browser compatibility must still be checked on the owner's Android device.

## Reports and detailed issues

- `docs/MASTER_BLOCKERS.md`: cross-repository academic diagnosis, reproducible completion gates, priorities and source links.
- `docs/FIXER_ARCHITECTURE_AND_COMPLETION.md`: actual worker contract, architecture, acceptance ladder and blocked next milestones.
- `docs/DEVPOST_SUBMISSION_CONCEPT.md`: Devpost-compatible tested demo scope and candidate event fit.
- Private `Spiritjcrow/Selma.0/docs/fixer/inventory/`: **all 79 open PRs and all 40 open issues** across 13 accessible repos, linked in 6 markdown files on the companion inventory branch.

## Status labels

`LOCAL_COMMIT_TESTED` is **not** `CI_PASSED`, `ANDROID_TESTED`, `DEPLOYED`, `PUBLISHED`, `PAID`, or `GOOD_TO_GO`. Those require their own evidence. The bot is not a 24/7 running supervisor or a general-purpose AI developer yet. Its first end-to-end local Git repair is implemented and tested with real process execution rather than a fake "success" response.