# SelmaOS first-run wizard: rootless/offline recovery QA v0.1

Scope: draft PR #87 / issue #51. This is a **manual, owner-authorized test plan**, not evidence that a device, model, browser, or GitHub Actions runner has executed. It does not alter runtime policy, install software, open a network interface, or grant permissions.

## Evidence tiers

- **Source/portable:** exact commit SHA and checked-in test output, including Python version, exit code, test counts and skipped cases. A reconstructed or isolated harness must be labeled as such.
- **Android/Termux:** owner-authorized, rootless Android 13+ device; record non-sensitive Android version, Termux/Python versions, commands, observed responses and timestamps. Do not record device identifiers, private file paths, access tokens or screenshots containing secrets.
- **Offline/model:** disable external internet for the test only with device-owner approval. Local wizard and chat are separate: a 202 `launch_pending` response with `ready:false` is **not** proof of a healthy runtime or functioning local model.
- **CI:** a GitHub Actions run with `startup_failure` and **zero jobs** is BLOCKED, not PASS or FAIL of test code. Track #26; do not retry repeatedly without changed evidence.

## Portable checks (from the repository root)

```sh
python3 -m py_compile SELMA0_ANDROID_AGENT_V1/selma0_first_run_android_v1.py
python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_setup*.py' -v
bash -n SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh
```

Record the exact commit and output/exit status for **each** command. Tests that mock `Popen` or run synthetic child scripts are not a real Selma runtime or Android acceptance test.

## Disposable device smoke, only with owner approval

1. Confirm the feature branch/commit, use a **separate** Termux test checkout and a newly created, empty test home. Do not reuse or overwrite the normal Selma data directory. Never run as root or install an unknown APK.
2. Set `SELMA0_BASE_V1` to that private test home, then launch `python3 SELMA0_ANDROID_AGENT_V1/selma0_first_run_android_v1.py` from the checkout. Verify the server binds **only** `127.0.0.1:8766`; do not expose the port over LAN or through a tunnel.
3. Open `http://127.0.0.1:8766` in the device browser. Verify the diagnostics report observed RAM/storage or `unknown`, reduced-motion mode stops animations, and the scene is explicitly fictional rather than GPS/AR.
4. In the disposable test home, verify invalid preference keys and an unauthorized `/start` POST fail closed. Never paste or publish the setup token. Do not submit real credentials, device identifiers or private recordings.
5. With the runtime script missing in a **disposable copy**, verify HTTP 503 and no saved preferences. Restore the script; confirm retry is possible. A normal checkout must remain intact.
6. With a **synthetic failing child**, verify an immediate exit or spawn failure returns 503, rolls back preferences, and permits retry. For symlink/hardlink log tests, use only unrelated synthetic files inside the test home. Do not manipulate production files.
7. On an authorized real launch, record the `/start` HTTP status and `ready` value. If it returns 202/`launch_pending`, check the **actual** local chat endpoint separately and record success, unavailable/no-model, or failure. A reachable wizard page alone does not prove inference.
8. Stop the test processes, confirm no unintended background child remains, and preserve diagnostic evidence before any **owner-reviewed** cleanup. Do not automatically delete the test home or the user's existing preferences.

## Known gap and recovery rule

The current startup wait is only **1.5 seconds**. A child that crashes later may leave saved preferences and block a new `/start` attempt with HTTP 409. Do **not** automatically delete preferences, kill an unknown PID, or retry launch based only on a stale UI. Record the exact process/HTTP/log observations; have the owner inspect the disposable test home before manual recovery. Durable readiness/liveness and post-start crash recovery require a separate reviewed implementation and regression tests.

## White → UltraViolet acceptance record

Record: `task_id`, `handoff_nonce`, `expected_base_sha`, `expected_head_sha`, `actual_head_sha`, `scope`, `owner_role`, `state`, `dependencies`, `evidence`, `tests: PASS/FAIL/NOT_RUN`, `next_owner`, `next_action`. A same-account logical White review is **not** an independently authenticated phone test. Keep PR #87 draft and do not merge/deploy until applicable independent review, real CI evidence or an explicit documented owner exception, and authorized device acceptance are available.

Do not duplicate Sol Red #43, compaction #85/PR86, Kimi #83/PR84, Dungeons & Crows or Chrome bounty work. Issue #88 is the cross-lane deduplication ledger; #51 owns wizard-specific defects.
