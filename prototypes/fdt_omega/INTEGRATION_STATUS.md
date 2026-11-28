# SelmaOS/Wisdmux FDT-Omega stabilization decision — 2026-11-11

## Decision

1. Canonical protocol string: `FDT-Omega` (master blueprint). Accept `FTD-Omega` only as a **separately signed wire alias** for compatibility. A relay MUST NOT rewrite the protocol field of a signed message.
2. Restrict optimization loops to telemetry/observational proposals in current prototype. Require explicit and independently validated approval for protocol changes, grants, deployments, and monetary transactions.
3. No migration of working production services, editing of current deployment manifests, or key rotation without staged verification.
4. For a locally verified signature/provenance fault, reject input and return `freeze_node=True` for integration into an existing authenticated supervisor. Prototype has no access to an active node and cannot physically freeze one.
5. Ordinary network degradation triggers alert/retry with bounded backoff; it must not unilaterally authenticate a compromised node or auto-resume a security-frozen node.
6. No real-money settlement, wallet transfer, OAuth data access, payment-provider debit, cloud sync or automation beyond recorded paper-ledger checks in this change.

## Test evidence

Executed locally: `PYTHONWARNINGS=error::ResourceWarning python -m unittest discover -s tests -v` -> **15 passed**, after closing all SQLite connections; `python -m compileall -q prototypes tests` passed.
No network/Android/Termux/CI integration verified. No active peer trust store exists. System is **prototype-only**.

## Follow-up acceptance gates

- Trusted node identity + key enrollment + revocation + secure persistent replay state integrated with #43 authenticated sessions.
- Complete canonical JSON interoperability specification and cross-language golden vectors.
- Authenticated telemetry sink with append-only incident records and operator-visible status.
- Per-node latency baselines plus explicit SLO thresholds; graceful degrade via retries, circuit breakers, and bounded queue, without unauthorized execution.
- Branch-only PR reviewed and independently tested on actual Android and cloud node before merge. Rollback documented.