# SelmaOS current state

Observed: 2026-08-31T23:19:28Z  
Canonical repository: Spiritjcrow/Selma.0 (private)  
Evidence baseline: main at e429da887eb183981d954a39450886b335a5e9b5

This report is a WP-01 evidence snapshot. It replaces branch descriptions and prior test claims only for the exact revision and environment recorded below. It is not physical-device evidence.

## Repository inventory

- Default branch: main
- Recursive tree: 61 entries, 44 blobs, 173,217 bytes of text/source content
- Open issues: #1, #3, #4, #15, #16, and #17
- Open pull requests: #5, #6, #8, #12, #13, and #14; all are drafts
- Branches: 14 total, including main
- Current-main native application: Android Gradle project at SELMA0_ANDROID_NATIVE_V1/
- Current-main runtime: Python/Termux project at SELMA0_ANDROID_AGENT_V1/

The machine-readable branch disposition is in docs/architecture/branch-migration-map.v1.json.

## Reproduced checks

Environment:

- Python 3.12.13
- OpenJDK 17.0.20
- Gradle: unavailable
- Android SDK: unavailable

Results on a reconstruction of the exact baseline:

| Check | Result | Evidence |
|---|---|---|
| Python syntax | PASS | Every repository Python file compiled with python3 -m py_compile |
| Shell syntax | PASS | Every repository shell file passed bash -n |
| JSON syntax | PASS | Every repository JSON file loaded with the Python standard library |
| Agent compile | PASS | python3 -m compileall -q SELMA0_ANDROID_AGENT_V1 |
| Command/device regressions | PASS | 55/55 unittest cases |
| Isolated smoke test | PASS | Runtime started on loopback, reported 19 registered tools, executed no device effects or sensitive scans, then stopped |
| Android lint/unit/APK | BLOCKED | The checkout has no Gradle wrapper; this environment has no Gradle 8.9 or Android SDK 35 |
| Owned Android install | NOT RUN | Requires the owner's device and manual platform permissions |

Exact commands are in docs/architecture/REPRODUCING.md.

## CI truth state

GitHub Actions does not currently provide usable evidence:

- All 19 workflow runs observed on main between 2026-08-15 and 2026-08-27 ended as startup_failure.
- The latest main run is [33035267129](https://github.com/Spiritjcrow/Selma.0/actions/runs/33035267129).
- The API reports workflow path BuildFailed, an empty workflow name, and zero jobs.
- Current main has zero combined status contexts and zero check runs.

Because no job started, repository test or build changes alone cannot prove the account/repository Actions gate is open. The owner must inspect GitHub Actions permissions and any account billing/minutes restriction if the next branch again creates a zero-job startup failure. No billing or protected-setting change is authorized by this report.

## Implemented and partial foundations

### Command and permission control plane

The audited command registry, permission engine, replay protection, loopback HTTP boundary, and hash-chained audit exist on main and pass portable regression tests. Gate 1 must use them rather than creating another external-effect executor or permission path.

### Android/Termux runtime

The Python runtime, SQLite memory, local web UI, allowlisted Termux bridge, and measured-only CrowRF storage/derivation paths exist. Portable tests pass. Android command availability, permissions, radio observations, battery impact, and location behavior are not verified here.

### Android native application

The source on main is a small remote HTTPS WebView:

- it loads selma-official-companion.spiritjcrow1990.chatgpt.site;
- it has no local-worker integration;
- it has no foreground service, overlay, wallpaper, avatar renderer, or degraded-state UI;
- it denies every WebView permission request;
- it contains no AR/VR dependency.

This is not the rootless offline native shell described by issue #4 or PR #5/#13.

### Offline inference

The main router expects an OpenAI-compatible local endpoint at 127.0.0.1:8080, but main does not include a managed llama.cpp launcher. PR #12 contains a candidate lifecycle script and tests that must be ported after Gate 1 contracts are frozen. A real internet-disabled answer has not been observed.

### Memory/RAG

Basic SQLite conversation memory exists. The bounded FTS5/fallback RAG draft is on PR #6 and must be ported, then extended with provenance, trust labels, retention, edit, export, deletion, and corruption recovery.

### Voice and live avatar

No verified offline wake/VAD/ASR/TTS loop, barge-in controller, signed avatar pack, live renderer, lip-sync runtime, overlay, or wallpaper exists on current main. The approved portrait remains an identity reference, not runtime evidence.

## Immediate blockers

1. GitHub Actions produces zero-job startup failures, so CI is not evidence-bearing.
2. The current main checkout lacks a Gradle wrapper and this environment lacks Gradle/Android SDK, so Android tasks cannot be reproduced locally.
3. Six draft PRs diverge from current main and must not be merged as-is.
4. Physical Android acceptance requires the owned Moto G Play 2023 and explicit manual permission grants.

## Gate 1 increment in this branch

This branch implements issue #15's first increment without moving existing implementations:

1. versioned architecture manifest;
2. model, memory, voice, avatar, device, notification, storage, process, network, and presentation protocols;
3. fail-closed null adapter;
4. generated support matrix;
5. contract tests for denial, timeout, cancellation, unavailable capability, offline boot, and shutdown.

The 15 contract tests pass locally. Gate 1 remains open until the branch receives usable CI evidence and the contracts are merged to main.
