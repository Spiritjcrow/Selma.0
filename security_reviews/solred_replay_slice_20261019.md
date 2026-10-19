# Sol Red: replay admission prototype (2026-10-19)

Issue: #43. This is a **test-only design handoff**, not a production authorization fix.

Confirmed in main: `SELMA0_ANDROID_AGENT_V1/selma0_runtime_command_core_android_v1.py` accepts JSON `approved`/`confirmed` flags and has an unconditional `approved=True` incident path. Host/Origin checks are not client authentication.

Isolated fixture checks (local, disposable SQLite): 3 passed:
- single-use nonce survives reopening the ledger
- token bound to client, session, tool and canonical arguments; expiry enforced
- tampered signature rejected

Required before integration:
1. Provision per-install authenticated native client identity and verify session liveness.
2. Only the trusted native UI may issue approval after a real user gesture; never let HTTP callers mint approvals.
3. Store approvals and operation states in an owner-only SQLite ledger with transactional admission and idempotency.
4. Design recovery for crash after admission but before/after side effects; nonce consumption alone cannot guarantee exactly-once external effects.
5. Use a monotonic deadline for same-boot timing and authenticated wall-clock policy across restarts; rotate keys without reopening replay.
6. Protect all private GET/POST routes, enforce exact browser origins, and preserve legitimate UI and offline operation.
7. Run native Android QA and full repository tests before considering merge.

No runtime behavior, deployment, account configuration or production data was changed.
