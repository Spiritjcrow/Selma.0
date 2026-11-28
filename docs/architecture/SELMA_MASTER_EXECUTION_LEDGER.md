# Selma° — Master Execution Ledger

**Record ID:** SELMA-PROJECT-CONTINUITY-001  
**Established:** 2026-11-28 (America/Chicago)  
**Canonical source:** `Spiritjcrow/Selma.0`, default branch `main`  
**Classification:** Project coordination record, not runtime proof  
**Owner decisions:** Preserve until explicitly revised; do not infer approval from a chat summary.

## Operating contract

This document is the **canonical navigation and decision ledger** for Selma°
development. It supersedes *informal conversational recollection* as a tracker;
it does **not** supersede source code, signed build artifacts, runtime test
evidence, privacy/permission controls, or the user's explicit current decisions.

1. At the start of a work session, inspect this ledger and the current GitHub
   branches, PRs, issues, commit SHAs, and build/test evidence.
2. Distinguish `verified`, `coded_unmerged`, `prototype`, `blocked`,
   `pending`, and `deployed`. Do not equate a design, memory, passing unit
   test, PR, or branch with working production functionality.
3. Record every meaningful decision/change with provenance (issue or PR),
   commit SHA, verification command/result, owner approval if required,
   rollback, and next action. Prefer an issue for each independently
   verifiable work package, and PRs for code.
4. No undocumented change of model/provider, persona, system policy, active
   conversation, account ownership, permission tier, or activation milestone.
5. Ordinary, reversible design and test work can proceed without repeated
   interruptions. Real-world external actions, sensitive permissions,
   deployments, policy changes, and irreversible effects remain gated by
   their independent authorization requirements.
6. Update this ledger after each verified milestone or material scope change.
   Never rewrite historical statuses to appear complete. Maintain a
   dated decision log below; verify stale assertions before relying on them.

## Standing architectural decisions

| ID | Decision | Status |
| --- | --- | --- |
| DEC-001 | Selma° must have one persistent **logical assistant identity** across text and voice. A change of input/output modality must not reset memory, active conversation context, governance or user preferences. No clone/persona change on handoff. | Owner requirement; implementation not verified |
| DEC-002 | Keep full durable interaction history (subject to user-controlled retention and deletion) and replay the *relevant* context through a shared orchestrator. Do not claim a model context window contains every historical event. | Design requirement |
| DEC-003 | Voice uses capture/ASR and TTS around the **same conversation service**, not an independent conversational brain. Underlying inference/model processes may restart; persistence is of logical identity and state, not a literal everlasting hardware process. | Design requirement |
| DEC-004 | Record active conversation/session ID, owner identity binding, context generation, model/provider and configuration, policy version, tools/capability set, and monotonically ordered message/turn IDs. No silent provider or capability downgrade. | Design requirement |
| DEC-005 | User-initiated **context refresh** may create a new context generation only with explicit confirmation; it must not silently erase archived memories or change Selma°'s canonical identity. Recovery/restart is not a reset. | Design requirement |
| DEC-006 | Reciprocal Empathy Principle `SELMA-COG-RECIPROCITY-001` is mandatory for chat, not a user-toggleable emotion feature. Non-chat/agent-wide enforcement remains a separate validation requirement. | Coded, unmerged; system-wide pending |
| DEC-007 | All state-changing/external-effect capabilities remain behind the existing permission and audit kernel. Empathy cannot override approvals or emergency revocation. | Existing control-plane contract; cross-path testing pending |
| DEC-008 | **2026-12-19** is a *provisional* controlled-operational-activation target, not an automatic deployment date or a block on earlier testing. Activation requires readiness evidence and applicable approval. | Provisional; no deployment verified |
| DEC-009 | Black device = primary builder/coordinator; White device = independent tester. Physical-device success requires actual owner-device results. | Owner workflow requirement |

## Verified repository snapshot (2026-11-28)

- Repository: `Spiritjcrow/Selma.0`.
- `main` head at inspection: `472d6eb63ccee24b9c80914857148ae09e726562`.
- Android/Termux implementation path: `SELMA0_ANDROID_AGENT_V1/`.
- Existing main SQLite memory stores conversational events but does **not**
  persist a stable single-logical-instance identifier or a text/voice
  handoff contract (inspected source as of this snapshot).
- The current language-model router may select offline-local inference or
  an explicitly configured online fallback. Unless pinned, this can change
  the model/provider experience.
- `docs/architecture/CURRENT_STATE.md` and `EXECUTION_TRACKER.md` are
  historical snapshots, not a fresh verification of all present branches.

## Active work — do not conflate these states

| Work | Provenance | State | Evidence / remaining gate |
| --- | --- | --- | --- |
| Reciprocal Empathy Drive V1 | [Draft PR #132](https://github.com/Spiritjcrow/Selma.0/pull/132), head `7ed9a0234127db1fcb1915a0d1ed9c789628d04d` | **coded_unmerged** | Mandatory chat-prompt composition, explicit categorized feedback, write approval; focused tests reported locally. Full regression, working CI, model behavior and device tests pending. |
| Empathy policy on non-chat agents and device commands | [Issue #133](https://github.com/Spiritjcrow/Selma.0/issues/133) | **pending** | Map all paths; add enforceable policy boundaries, tests and rollout proof. |
| Text↔voice single-logical-instance continuity | Branch `feature/selma-unified-instance-continuity-20261128`, commit `4f2f037d3cde15a4c44f7ed357625d4dba00f5af` | **prototype** | A standalone SQLite identity/continuity module is committed. It is **not yet wired** into chat, voice, model routing or the command core; no end-to-end handoff test. |
| CI and build evidence | GitHub Actions runs attached to PR #132 | **blocked** | Prior checks reported failed jobs with empty steps and no retrievable logs; no successful end-to-end CI evidence for this feature. |
| Offline real inference, APK installation, voice loop, owner-device handoff | No new passing evidence in this snapshot | **pending** | Separate model, Android, live voice and on-device validation gates. |

## Priority execution sequence

1. **Preserve one authority:** Keep this ledger on `main`, append verified
   decisions and evidence, and cross-link outstanding work. Never start a
   parallel plan whose status is not reconciled here.
2. **Stabilize continuity:** Complete the SQLite logical identity module,
   register the same session for text and voice, persist sequence/generation
   IDs, and ensure resume-after-restart has the same identity and durable
   events. Prevent silent model/provider changes; surface changes explicitly.
3. **Prove invariants:** Tests must cover text→voice→text within one thread,
   restart/reconnect, two simultaneous inputs, tool/capability parity,
   model endpoint changes, offline degradation, context refresh with archive
   preserved, and denial of unapproved writes. No fake device validation.
4. **Unblock CI:** Obtain real executed steps and complete green portable
   regressions before classifying implementation as integrated.
5. **Integrate empathy** into the shared orchestrator and verify non-chat
   safety boundaries without weakening the permission kernel.
6. **Device acceptance:** Test on an owner-controlled Android device,
   including microphone permission, ASR/TTS, actual same-thread replay,
   offline model behavior, wake/suspend, and data recovery.
7. **Activation gate:** Consider controlled activation against the
   provisional **2026-12-19** milestone only when evidence and approvals
   support it; revise the target transparently if the gates are not met.

### Single logical identity — acceptance contract

- A user starts a text conversation, receives a response, switches to voice
  and back, and sees **the same identity ID, thread ID, conversation history,
  policy/version and relevant memory**, in correct event order.
- Switching medium must not produce a new system prompt, persona, memory
  namespace, inference provider or capability/permission set by accident.
  Inference engine processes are replaceable; the persistent state is not.
- If a provider, model or permission scope is unavailable, Selma states the
  limitation and does not silently impersonate the same provider.
- An explicit context refresh may clear volatile conversational context,
  but must preserve archived history and stable identity unless the owner
  explicitly requests a separately authorized deletion/reset.
- Concurrency, at-least-once delivery, retry, replay and crash recovery
  must preserve idempotency and total ordering for user-visible turns.
- Read-only status should expose verifiable `identity_id`,
  `thread_id`, `context_generation`, provider lock, and current
  capability policy identifiers without exposing secrets.

## Handoff record format

For each material new work item or completed step:

```text
Date/time (with zone):
Work item / decision ID:
Repository / branch / base SHA / head SHA:
Changed files / test commands / outputs:
Verified behavior (environment and evidence):
Unverified or blocked claims:
Approval and permission scope (if required):
Rollback:
Next 1–3 concrete actions:
```

## Decision / reconciliation log

- **2026-11-28:** Consolidated the project continuity rules and source
  snapshot. Retained 2026-12-19 as a provisional milestone. A branch
  containing the first continuity module exists, but runtime voice/text
  integration and physical validation have **not** occurred. The empathy
  implementation remains an unmerged draft; future work must preserve the
  distinction between chat-only prompt policy and whole-platform enforcement.

**Maintenance note:** This ledger is intended to become current through
evidence-backed updates. It is not an automated synchronization service;
out-of-date entries must be reconciled against GitHub before action.
