# Selma Reflex Continuity Engine v1

Status: architecture contract / non-destructive resilience layer

## Goal

Turn recurring blockers into reusable response patterns so Selma/Sol can react quickly, safely, and consistently when expected or unexpected problems appear.

The engine is optimized for:
- immediate diagnosis;
- smallest safe workaround first;
- multiple fallback paths;
- low-friction recovery;
- offline/local continuation;
- preserving verified work;
- avoiding repeated dead ends.

## Core reflex loop

Every blocker or degraded condition enters the same bounded loop:

1. detect;
2. classify;
3. preserve current good state;
4. identify the narrow failing dependency;
5. generate ranked responses;
6. choose the lowest-risk/highest-leverage path;
7. execute only if already authorized;
8. verify;
9. record evidence;
10. queue unresolved follow-up;
11. continue independent work.

## Response ladder

For each failure, generate at least these response classes when applicable:

- FIX: repair the direct cause;
- WORKAROUND: bypass only the failing component without bypassing security;
- FALLBACK: switch to a simpler local/offline path;
- ALTERNATIVE: use another compatible provider/tool/runtime;
- DEFER: preserve state and queue the blocked step;
- ISOLATE: quarantine the failing module and continue elsewhere;
- REBUILD: recreate only the damaged component from verified sources;
- ROLLBACK: return to the last known-good state;
- ESCALATE: request human approval only when required.

The engine must not invent a bypass for OS, MDM, carrier, account-security, or provider controls.

## Decision scoring

Candidate responses are ranked by:

1. safety;
2. reversibility;
3. probability of success;
4. time to restore useful function;
5. offline capability;
6. dependency count;
7. implementation complexity;
8. evidence quality;
9. maintenance cost.

When two options are equivalent, prefer the simpler and more local one.

## Reflex memory

Recurring blockers should become reusable patterns.

Each pattern records:
- trigger signature;
- affected subsystem;
- known cause classes;
- verified fixes;
- verified workarounds;
- unsupported attempts;
- prerequisite checks;
- rollback steps;
- validation tests;
- evidence timestamp;
- confidence state.

A prior pattern may accelerate diagnosis but never upgrades current evidence automatically.

## Blocker classes

Initial canonical classes:

- CI admission failure;
- dependency unavailable;
- permission denied;
- capability unsupported;
- network unavailable;
- provider unavailable;
- authentication expired;
- storage full;
- corrupted artifact;
- version drift;
- incompatible runtime;
- device-policy restriction;
- rate limit;
- merge conflict;
- stale state;
- missing model/asset;
- offline mode;
- thermal/memory pressure.

## Continuity rules

A blocker in one subsystem must not freeze unrelated work.

Examples:
- CI blocked -> run portable/local tests and source validation;
- Android permission denied -> preserve text/local UI path;
- remote storage unavailable -> queue sync and continue local work;
- network lost -> continue offline tasks and revalidate before replay;
- provider write blocked -> generate patch/package and keep mutation queued;
- model missing -> keep runtime/UI tests separate from model-dependent tests.

## Future-proofing

For every new feature, define before release:

- required dependencies;
- optional dependencies;
- no-network behavior;
- no-permission behavior;
- low-storage behavior;
- low-memory behavior;
- provider-loss behavior;
- rollback path;
- test evidence required;
- alternate implementation path.

This converts surprise failures into expected state transitions.

## Truth states

All generated responses must be labeled:

- REAL: directly verified;
- PREVIEW: proposed/dry-run;
- INFERRED: reasoned from evidence;
- UNVERIFIED: not yet evidenced;
- BLOCKED: cannot proceed;
- DEGRADED: usable but reduced capability.

## Automation boundary

Automatic execution is permitted only for low-risk, reversible, already-authorized development and verification steps.

Explicit human approval remains required at execution time for:
- publishing/releases;
- protected-branch merge;
- account-security changes;
- credential rotation/revocation;
- deleting data;
- public exposure;
- purchases;
- widening permissions;
- bypassing platform/provider controls.

## Reflex output contract

When a blocker occurs, Selma should produce internally:

```text
BLOCKER
KNOWN_GOOD_STATE
LIKELY_CAUSE
FIX
WORKAROUND
FALLBACK
ALTERNATIVES
SAFE_ACTION_NOW
VERIFICATION
ROLLBACK
QUEUED_FOLLOWUP
TRUTH_STATE
```

User-facing responses may remain concise.

## First implementation slice

1. Typed Blocker and ResponseOption models.
2. Rule-based classifier for common blocker classes.
3. Candidate ranking/scoring.
4. Persistent local pattern store.
5. Safe-action executor for reversible dev/test steps.
6. Offline queue with revalidation.
7. Evidence journal integration with Sol Security Fabric.
8. Regression tests proving a blocked subsystem does not halt unrelated work.
