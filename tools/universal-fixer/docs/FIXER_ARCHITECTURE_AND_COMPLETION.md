# Selma° Universal Fixer — executable recovery architecture and finish-line contract

## 1. Product objective

Turn a fragmented software estate into a source-grounded **plan → reproduce → patch → validate → commit → review → publish → deploy → verify → close** pipeline. The user should receive brief A/B/C/D or YES/NO approval requests only at consequential boundaries. The Fixer must run useful read-only work and approved low-risk repairs without requiring the user to write code or manually relay logs.

**Honest status:** v0.2 implements repository inventory (GitHub REST), local SQLite evidence registry, browser-readable report, immutable source-digest approval, and a **working RED→GREEN local Git repair worker**. It does not yet contain a general-purpose AI code generator, persistent cloud worker, Google OAuth UI, portable device executor, GitHub PR publisher, remote CI repair, or automatic financial settlement system. Those are pending independently testable milestones, not fake UI buttons.

## 2. Implemented local repair worker (v0.2)

1. Operator selects an owned, clean local Git checkout and a source-bound JSON repair plan.
2. Plan validates task identifier, 40-character base Git SHA, exact file SHA-256, UTF-8 patch target, no traversal/symlinks, one-and-only-one search match, allowed test command argv, and scoped commit message.
3. `repair-plan` prints SHA-256 of the canonical plan and exact tests/effects. A fresh plan is required after source changes.
4. `repair-run` requires the exact digest; creates a disposable **detached** worktree at the recorded commit; runs actual pre-fix tests and requires a failing baseline.
5. It applies the explicitly approved replacement once and reruns each required test. If any fail, **NO commit** is created, and an evidence record explains the failure.
6. If all pass, it creates a new `fixer/` branch and a real Git commit containing only the approved changed source file; preserves the existing base checkout.
7. It writes a **write-once** JSON record with exit codes, bounded test-output tails, new commit SHA, and `external_validation=NOT_RUN`. No push, merge, deployment, payment, device control or credential handling is performed by this worker.
8. It refuses to process dirty checkouts, changed source SHA, unsafe test command shape, stale approval, existing branch, existing result file, ambiguous patch, or unsupported file types.

Tests execute code from the checkout; only use on repositories you own/trust. This version has **no OS-level sandbox** and cannot prove arbitrary tests have no network or other effects. For production, run in a restricted container/VM without credentials/network by default.

### Complete local run

```bash
python -m unittest discover -s tests -v
python -m fixer repair-plan --repo /path/to/owned/clean/checkout --plan /path/to/approved-plan.json
# Review printed digest and exact patch scope; choose A only if desired.
python -m fixer repair-run --repo /path/to/owned/clean/checkout \
  --plan /path/to/approved-plan.json \
  --approve-digest <64-hex-plan-sha> \
  --evidence /path/outside/repo/repair-001.json
```

The plan is a strict JSON object with exactly these fields:

```json
{
  "task_id": "Spiritjcrow/Selma.0:issue:43",
  "base_sha": "a full 40-character SHA from git rev-parse HEAD",
  "change": {
    "path": "relative/source.py",
    "before": "the exact old source fragment",
    "after": "the exact corrected source fragment",
    "file_sha256": "SHA-256 of the complete current source file"
  },
  "tests": [["python", "-m", "unittest", "discover", "-s", "tests", "-v"]],
  "commit_message": "fix: describe the verified and scoped repair"
}
```

Values like `base_sha` must be real 40-hex data, and the file digest real 64-hex data; this snippet illustrates the schema, not a runnable synthetic source plan. A real plan is created only after examining current owned source. Do not paste sensitive source or credentials into another service.

## 3. Target production architecture

```text
GitHub + connected Drive + connected issue trackers (authorized)
                      |
             INGEST / PROVENANCE
              (source metadata)
                      |
         NORMALIZE + DEDUPE + GRAPH
        (immutable issue IDs, SHAs, DAG)
                      |
             SAFETY POLICY GATE
        (owner scopes, secret isolation)
                      |
          REPAIR WORKER (isolated)
    (reproduce -> patch -> test -> commit)
                      |
        INDEPENDENT VERIFIER / CI
     (real runner, emulators, device lab)
                      |
      REVIEWABLE PR + CHANGED EVIDENCE
                      |
          RELEASE/DEPLOYMENT GATE
      (signed artifact, rollback path)
                      |
     MONITOR / SELF-HEAL / CLOSE TICKET
                      |
            MOBILE OWNER INBOX
      [A Approve] [B Hold] [C Evidence] [D Reject]
```

A/B/C/D cannot grant authority from a model suggestion. In production approvals must be authenticated with trusted user presence, short-lived operation/arguments/artifact hash binding, replay protection and audit. Distinct permissions should exist for `read`, `propose`, `local repair`, `PR write`, `merge`, `deploy`, `device operation`, and `financial operation`. The last four are high-impact and require action-specific controls.

### Worker roles

| Role | Responsibility | Must never assume |
|---|---|---|
| Dispatcher | Normalize, dedupe, rank by critical-path and cost | `open PR = broken code`; trusted credentials in issue body |
| Reproducer | Find failing behavior and capture first `RED` evidence | Missing CI job means a test failed |
| Builder | Apply bounded patch in isolated worktree | Permission to overwrite main or another worker branch |
| Verifier | Run independent tests and confirm full acceptance matrix | One local test means physical Android/cloud passes |
| Security reviewer | Check auth, provenance, data scope, dependencies, regressions | Signed handoff means action authorization |
| Release operator | Package, sign, deploy and roll back approved releases | A local commit means store approval |
| Human owner | Approve high-impact decisions through authenticated A/B/C/D UI | Need to manually do routine tests or copy/paste logs |

## 4. Prioritized stages of a true autonomous Fixer

| Gate | Product component | Acceptance evidence | Current status |
|---|---|---|---|
| G0 | Audited inventory and dedupe | Every accessible repo's PR/issue indexed and stable links retained; live sync uses real credentials | PARTIAL: 13 repo connector snapshot and local REST reader; not a persistent service |
| G1 | Deterministic repair executor | Reproduce a real failing test; approved patch; green rerun; new Git branch+commit; no modification to main | **LOCAL VERIFIED**: test suite exercises real Git+unittest and negative cases |
| G2 | AI code synthesis | Task→hypotheses→minimal patch; executable against real source; automatic negative tests; approval/revert | NOT BUILT: requires selected LLM backend and resource budget |
| G3 | Repository write/PR agent | Push from authenticated scoped identity; create PR; log SHA; reviewers and comments; no force-push | NOT BUILT IN WORKER: present chat GitHub connector can write on user's behalf |
| G4 | Reliable test runners | Local CI, Docker sandbox, SDK/JDK/Gradle, Windows/Linux/Android test matrix and real runner proof | PARTIAL: local Python tests; Android/CI unverified |
| G5 | Mobile private approvals | Secure Google/passkey login and signed one-click A/B/C/D for a specific action | NOT BUILT; plain CLI and read-only browser report currently |
| G6 | Autonomous safe orchestration | Durable scheduler, lease fencing, idempotent recovery, bounded self-heal, per-workstream budget, alerts | NOT BUILT as a daemon; existing ChatGPT hourly automations are not continuous workers |
| G7 | Validated releases | Real install/health telemetry, canary rollout, rollback, acceptance evidence, issue closure | NOT BUILT |
| G8 | Regulated finance | Separate sandbox/prod ledgers, consent, anti-fraud, audit and settlement reconciliation | SIMULATION ONLY in ARIA; live micropayment settlement not enabled |

## 5. Why this won't repeat endless half-finished projects

- **One critical path.** No new architectural branch until a real Gate 1 fix is delivered; group duplicate reports and unify staged PR chains. End tasks by evidence, not optimism.
- **One failure taxonomy.** `SOURCE_FAIL`, `TEST_FAIL`, `DEPENDENCY_MISSING`, `RUNNER_NOT_ADMITTED`, `DEVICE_NOT_TESTED`, `AUTH_MISSING`, `PROVIDER_UNAVAILABLE`, `DATA_STALE`, `LICENSE_BLOCKED`, `SECURITY_BLOCKED`, `APPROVAL_PENDING`.
- **Automatic next action.** Every stop yields the smallest concrete step the current authorized worker can perform. If impossible because of external policy, stop retries and escalate to one clear user/provider action while working on independent items.
- **State continuity.** Store immutable issue ID+base SHA, task lease, patch digest, validation runs, audit events and artifact hash; do not regenerate a new plan every hour from memory.
- **Explicit kill switch.** Stop a worker or entire lane on signature failure, unauthorized action, exceeded resource budget, or unresolved policy violation; preserve logs and never auto-resume without validated recovery.
- **No false completion.** Dashboard labels must distinguish tested local worker, packaging proof, connected cloud endpoint and real device acceptance.

## 6. Release definition of done

A milestone is **GOOD_TO_GO** only if source change and tests are on the intended branch, required full integration suite passed, mandatory runtime/platform checks passed, privacy/security/IP checks passed, user approvals are valid for exact effect, a reproducible deployment exists where required, rollback is tested, and a human-readable evidence record is attached. If any required condition is unknown, state is `BLOCKED` or `IN_REVIEW`, never `COMPLETE`.

For the next slice prioritize **#43 authenticated approval boundary** and **#26 runnable CI** independently. Do not let work on a generic bot delay safety-critical source fixes or the first real Android APK milestone.