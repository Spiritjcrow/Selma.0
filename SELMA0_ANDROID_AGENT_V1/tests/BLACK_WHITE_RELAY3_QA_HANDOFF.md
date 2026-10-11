# SelmaOS Black → White QA → Black repair: relay 3

**Scope:** First-run wizard readiness gate only. No protected merge, deployment, or device operations.

## Evidence inspected
- First-run wizard branch `feature/selmaos-first-run-wizard-20261011`
- Readiness branches `fix/selmaos-wizard-ready-gate-20261011-a1` and `fix/selmaos-wizard-pid-readiness-relay2-20261012`
- Dual-agent branch `feature/selmaos-dual-agent-handoff-20261017`, draft PR #50, Android launcher PR #48
- Issues #49, #51 and canonical execution tracker #17

## Black Builder: reversible test slice
- Branch: `fix/selmaos-wizard-runtime-ready-relay3-20261011` (forked from relay 2).
- Commit: `230e4cd942915dd6000e1db73938348872bf1652`.
- Added: `SELMA0_ANDROID_AGENT_V1/tests/test_first_run_runtime_gate_contract_v1.py`.
- No production files changed. Rollback: abandon disposable branch or revert its test commit.

## White independent source inspection
Read actual GitHub branch files and executed seven source-contract assertions against fetched content:
- PASS: readiness helper compares response PID to spawned process PID.
- PASS: readiness helper targets `127.0.0.1`.
- PASS: QA regression file is present.
- FAIL: wizard does not import readiness helper.
- FAIL: wizard does not call readiness check before saving.
- FAIL: wizard does not stop failed child on readiness failure.
- FAIL: command-core status does not publish `runtime_pid_v1`.

**Result:** 3 PASS / 4 FAIL (connector-based source checks). These are not a Python unittest execution, GitHub Actions result, or Android device test.

Reproducible command after checkout:
`python3 -m unittest SELMA0_ANDROID_AGENT_V1/tests/test_first_run_runtime_gate_contract_v1.py -v`
Expected currently: failures until the readiness integration is implemented.
GitHub combined commit status: no statuses returned; CI not verified.

## Black repair (next owner)
1. Add `status["runtime_pid_v1"] = os.getpid()` to command-core status response.
2. Wire `wait_for_runtime_ready(child, timeout=15, port=8765)` into the wizard after `Popen`, before `save_preferences`; fail closed and clean up only the newly spawned child on timeout.
3. Add portable mock-process/HTTP tests proving no preference persistence on child exit, wrong PID, occupied port, or timeout; test successful ready path.
4. Preserve loopback-only, rootless Termux, offline-first behavior. Run actual unittest, Python compilation, and (when available) owned Android tests separately.

**Final gate:** FAIL. No merge. White QA remains next after Black repair.
