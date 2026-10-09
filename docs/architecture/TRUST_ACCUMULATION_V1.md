# Sol Ultraviolet: verified recursive trust (pilot v1)

## Invariant

**Evidence-backed personal trust is monotonic: verified gains only.**
A failed task, elapsed time, hardware throttling, lost connectivity, or a
collaborator going offline does not erase previously earned trust.

- Every verified success permanently contributes one scoped credit.
- Proof IDs are replay protected; a caller-provided verifier **must** verify
  authentic job outcomes, verifier identity and ownership independently.
- Self-verified records, verifier failures, duplicate proof IDs, and
  future-dated proofs cannot increase trust.
- Collaboration is reflected by distinct independently verified verifiers.
- A tier can stay level or rise, never fall. There is no expiry/decay routine.

| Tier | Verified successes | Distinct verifiers | Distinct days | Advisory max parallel read tasks | Advisory retries |
|---|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 1 | 0 |
| 1 | 3 | 1 | 1 | 2 | 1 |
| 2 | 10 | 2 | 2 | 4 | 2 |
| 3 | 25 | 3 | 5 | 8 | 3 |

These are recommended workload ceilings for **read-only, separately permitted**
tasks, not elevated permissions or guaranteed CPU/GPU capabilities.
Critical OS/system thermal limits can still reduce *actual execution rate*,
without decrementing historical trust.

## Boundaries and integration

Implementation: \`core/trust_budget.py\`; portable tests: \`tests/test_trust_budget.py\`.

This independent pilot performs **no tool execution**, **no approval issuance**,
**no user impersonation**, **no access-control decisions**, and **no hardware
overclocking**. All sensitive reads, writes, network effects and admin actions
remain subject to existing Selma command governance and FDT/permission checks.

No system uses this ledger by default: hook-up is a separate reviewed increment.
The record store is bounded and process-local (it is **not persistent** across
process restarts). Before production use, add a durable integrity-protected,
tamper-evident append-only store; implement real trusted proof-verifier adapters,
reconciliation after restarts, audit and controlled export; test cancellation,
resource budgets, device thermal behavior, and safety gates. Do not confuse
the nondecreasing model with deployed persistent trust.

Validate with:
\`\`\`bash
python3 -m unittest tests.test_trust_budget -v
\`\`\`

No hardware benchmark, security authorization upgrade, or cloud CI pass is
claimed by the introduction of this feature.
