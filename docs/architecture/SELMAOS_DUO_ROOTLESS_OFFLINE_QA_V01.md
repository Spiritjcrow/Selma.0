# SelmaOS dual-role rootless offline QA v0.1

**Scope:** PR #50 / issue #49, handoff validator only. This is a **manual test plan**, not a record that either phone, a second account, Termux, an Android app, or a local LLM was exercised. Rootless Android 13+ is the target; no AR, camera, microphone, network service, root, overlay permission, or installed model is required for the Python contract checks. Keep APK release work (#48) and authentication/security work (#43/#44) in their separate lanes.

## Gate 0: evidence and environment (no installation or account changes)

1. Tester independently opens the authorized private PR #50 and issue #49 in their **own** approved GitHub session. If that access or a second authenticated identity is absent, mark **BLOCKED**; a logical White role in the same automation is not an independent Tester.
2. On the Android 13+ device, confirm a local Python 3.11+ interpreter and an authorized copy of the exact PR head. Termux is **optional and not presumed installed**. If no compatible interpreter exists, mark on-device Python checks **NOT_RUN**, not PASS. Do not install packages or request new permissions solely to make this test pass.
3. Record UTC timestamp, non-sensitive Android version and Python version, GitHub identity **only if independently authenticated**, PR head SHA, working-tree cleanliness, and exact command output/exit codes. Do not post tokens, account recovery material, raw private logs, or identifying device information.

## Gate 1: contract-only smoke, while offline

If Gate 0 is satisfied, disconnect external network connectivity using ordinary user controls; do not disable device protections. From the checked-out repository root, run:

```sh
python3 --version
python3 -m unittest discover -s tests -p 'test_duo*.py' -v
python3 -m py_compile core/duo_handoff.py tools/selma_duo_validate.py
python3 tools/selma_duo_validate.py - <<'JSON'
[{"schema_version":1,"task_id":"SELMA49-QA-SYNTHETIC","repository":"Spiritjcrow/Selma.0","ref":"feature/selmaos-dual-agent-handoff-20261017","actor_role":"builder","status":"submitted","artifact":"commit:synthetic-fixture","evidence":[],"summary":"Synthetic offline smoke; no phone handoff claimed"}]
JSON
```

The last command must exit `0` and print `{"ok": true, "state": "awaiting_tester", "task_id": "SELMA49-QA-SYNTHETIC"}` (JSON key order may differ). `awaiting_tester` is expected: no independently authenticated Tester record exists in this fixture. Compilation/test commands must exit `0` for local contract **PASS**; otherwise record **FAIL** with a minimal reproducible input and return to Black.

## Gate 2: distinct observations, no implied promotion

| Check | Required evidence | Classification without evidence |
| --- | --- | --- |
| Offline Python contract | Exact SHA, interpreter, commands, exit codes, observed JSON | NOT_RUN |
| Rootless Android 13+ | Actual owned-device environment and command outputs | NOT_RUN |
| No AR dependency | Source review plus Android runtime observation | BLOCKED if runtime untested |
| Independent White review | Separately authenticated account, actual review/test record | BLOCKED |
| CI job execution | Workflow run URL, nonempty job ID, completed steps | BLOCKED while #26 has `startup_failure` / zero jobs |
| Local LLM / full app boot | Separate model/runtime evidence, if tested | NOT_RUN; out of scope for this contract |

A validator output `tester_reported_pass` is **only a claim encoded in supplied JSON**, not proof of phone identity, a successful app launch, or approval to merge. A real independently authenticated White review must inspect the actual Builder SHA, reproduce available checks, and report its own observations.

## Gate 3: concise handoff record and next action

In existing PR #50 or issue #49, post at most one nonduplicate checkpoint for a material change: UTC timestamp; chain/task/sequence; intended role vs actual authenticated GitHub account; PR branch and full SHA; commands and exit codes; links to evidence; each check marked **PASS/FAIL/BLOCKED/NOT_RUN**; uncertainty; `next_owner` and `next_action`. Do not create a new issue or infer a SHA-256 chain link without computing and checking the exact prior canonical bytes.

**Failure routing:** A reproducible contract failure goes to Black for one bounded repair. Missing independent account/device evidence goes to the owner-approved tester. GitHub Actions zero-job startup goes to issue #26, not to a fictional failing test. Do not merge, deploy, expose a network endpoint, or broaden permissions on the strength of this checklist.
