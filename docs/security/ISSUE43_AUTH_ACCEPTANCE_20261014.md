# Issue #43: Authenticated local HTTP acceptance contract (Sol Red, 2026-10-14)

Status: **review-only evidence; no runtime integration or production fix**. This document does not authorize deployment or changes to live user data.

## Boundary
Both `selma0_runtime_android_v1.py` and `selma0_runtime_command_core_android_v1.py` expose sensitive API routes. Loopback, Host and Origin checks alone do not establish caller identity. Client booleans (`approved`, `confirmed`) are not evidence of user approval.

Required before resolving #43:
1. Authenticate private GET and all POST routes using a securely provisioned local owner identity. Keep public UI and a minimal health check.
2. Require separate, short-lived, single-use approval evidence bound to authenticated session, operation, canonical arguments and request ID. Reject replay, expiry and cross-session use without consuming another session's ticket.
3. Reject missing/wrong browser Origin and Host ports; never broaden binding to bypass authorization.
4. Preserve legitimate chat, safety, incident, SOS, Replika preview/import and tool flows through a trusted UI, with independent QA before enabling real side effects.
5. Never place tokens or approval proofs in URLs, logs, repo, client persistent storage or issue comments.

## Local fixture evidence (not runtime or Android verification)
- 64 Python fixture/diagnostic checks on disposable inputs (60 security/contract/retention tests and 4 privacy diagnostics). Privacy diagnostic passes indicate gaps, **not** security success.
- Exact PR #41 source: 4 Python tests passed; exact PR #42 policy: 13 Java tests passed.
- Synthetic SQLite diagnostics show default 0644 file creation under umask 022 and a 0600 explicit-creation alternative. Parent directory permissions and device deployment remain unverified.
- Current `main` code/config pattern scan: 55 text files; no credential literal or PoeLLM/LiteLLM indicators matched the selected patterns. Nine mutable major-version GitHub Actions `uses` references across two workflows. Pattern negatives do not prove no secrets.
- Historical snapshots `658fc493fb47` (2026-09-01) and `6b59de61532b` (2026-08-27) were tree-compared with `main`; only three differing workflow blobs required additional pattern scans. Complete reachable history, advisories and dependencies remain uncovered.
- Actions run `38514643526` (2026-10-14 05:03:55 UTC): `startup_failure`, zero jobs; no GitHub CI test execution.

## Unresolved
**HIGH**: #43 authenticated integration missing; private status, memory and audit GETs, caller-approved writes and alternate runtime remain exposed to untrusted local callers in source. No exploitation or remote compromise is claimed.

**Privacy**: audit redaction handles only exact sensitive keys and can preserve unstructured results; SQLite WAL/retention and file permissions need review before a backward-compatible migration.

**Draft PRs**: #41 and #42 local contract tests pass; WebView main-frame/subresource/navigation behavior and Android builds remain unverified.

**CI**: #26 startup admission is blocked. Do not treat local tests as CI success.

Next: stage bounded authority implementation on a separate review branch, then integrate both handlers with a trusted local pairing/approval UI and disposable end-to-end tests. No merge, production deployment, account changes or privileged device actions.
