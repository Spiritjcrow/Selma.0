# Wisdomux Revival v1

Status: reconstructed foundation from prior project evidence and current SelmaOS contracts.

## What Wisdomux was

Wisdomux was conceived as a Termux-like, hands-free Natural Language Operating System and multi-agent development environment with:

- a Lead PM / natural-language interpreter;
- API orchestration;
- autonomous build/test/deploy workflows;
- React 18 + Vite + Tailwind dark PWA;
- Node + Express + WebSocket backend;
- SQLite via better-sqlite3;
- Zustand client state;
- Web Push;
- conversational commands plus Web Speech voice input;
- Crew Roles for Lead Architect, Frontend, Backend, DevOps, Security, Data, and QA;
- automatic crew-role assignment;
- a Boardroom emergency halt / context-conflict resolution / resume mechanism;
- GitHub autonomous commits with a proof-of-work ledger;
- push notifications;
- Termux integration, including a previously referenced termux_socket_bridge.

## Revival objective

Wisdomux now becomes the multi-agent coordination plane for SelmaOS rather than a separate competing runtime.

SelmaOS owns device/runtime execution, local inference, permissions, offline operation, memory, capability enforcement, and recovery.

Wisdomux owns:
- agent identity and presence;
- task decomposition;
- work claiming;
- inter-agent messaging;
- shared queues;
- dependency graphs;
- handoffs;
- conflict resolution;
- status aggregation;
- proof-of-work;
- Boardroom escalation;
- project-level orchestration.

## Relationship to current architecture

- SelmaOS: runtime and device authority plane.
- Wisdomux: coordination and collaboration plane.
- Sol Blue: defensive observation, diagnostics, evidence.
- Sol Red: capability-bounded defensive remediation.
- KAI: higher-level synthesis, planning, prioritization, and cross-project reasoning.
- SUWAF: workspace isolation, authority, provenance, runner/foreman/inspector boundaries.
- Reflex Continuity Engine: fix/workaround/fallback/alternative/isolate/rebuild/rollback routing.
- FDT / WingDingynouse: deterministic authorization layer for consequential actions.

Wisdomux must never grant itself more authority than the underlying capability system allows.

## Canonical agent lifecycle

Every agent uses the same state machine:

```text
OBSERVE -> CLAIM -> PLAN -> EXECUTE -> VERIFY -> REPORT -> HANDOFF
```

Any step may transition to:

```text
BLOCKED -> REFLEX -> RETRY | FALLBACK | DEFER | ESCALATE
```

## Core message envelope

Every inter-agent message carries:

- protocol_version;
- message_id;
- correlation_id;
- project_id;
- task_id;
- parent_task_id;
- sender_agent;
- recipient_agent or broadcast scope;
- intent;
- truth_state;
- authority_scope;
- required_capability;
- dependencies;
- evidence_refs;
- payload;
- created_at;
- expires_at;
- requested_action;
- approval_state;
- rollback_ref.

Truth states are shared with SelmaOS:

- REAL
- PREVIEW
- INFERRED
- UNVERIFIED
- BLOCKED
- DEGRADED

## Boardroom v2

Boardroom is the arbitration path for:
- agent disagreement;
- conflicting evidence;
- duplicate task claims;
- dependency deadlock;
- authority ambiguity;
- risky changes;
- human-required approval.

Boardroom may halt a single task or workstream without freezing unrelated projects.

## Crew Roles v2

Default roles:

- Lead Architect
- Coordinator / PM
- Frontend
- Backend
- DevOps
- Security
- Data
- QA
- Documentation
- Release
- Research
- Recovery / Continuity

Roles are capabilities, not personalities. Any compatible model/agent may fill a role if policy permits.

## Offline-first behavior

Wisdomux must remain useful without network access:

- local SQLite queue;
- append-only event journal;
- local agent registry;
- local WebSocket or Unix/domain-socket-compatible transport where available;
- queued remote sync;
- revalidation before replay;
- no retry storms;
- no security weakening to restore connectivity.

## Planned source layout

```text
wisdomux/
  README.md
  backend/
    server.js
    agentEngine.js
    db.js
    boardroom.js
    capabilityBroker.js
    taskQueue.js
    proofLedger.js
    adapters/
      selmaos.js
      github.js
      termux.js
  frontend/
    src/
      App.jsx
      components/
      hooks/
        useWebSocket.js
        usePush.js
      store/
  protocol/
    agent-message.schema.json
    task.schema.json
    capability.schema.json
  db/
    migrations/
  tests/
```

## First restoration slice

1. Freeze the protocol schema.
2. Create SQLite task/event/agent tables.
3. Rebuild WebSocket message transport.
4. Rebuild Crew Role assignment.
5. Rebuild Boardroom halt/resume arbitration.
6. Connect SelmaOS as the first runtime adapter.
7. Connect GitHub as a scoped provider adapter.
8. Add proof-of-work and provenance journal.
9. Restore Termux bridge as an optional local adapter.
10. Add non-destructive end-to-end tests.

## Safety boundary

Automatic development actions are limited to low-risk, reversible, already-authorized work.

Human approval remains required at execution time for:
- publishing or releasing;
- protected-branch merge;
- deleting data;
- changing account security;
- credential rotation/revocation;
- widening permissions;
- public service exposure;
- purchases;
- bypassing OS/provider controls.

## Evidence status

REAL:
- historical architecture and role model reconstructed from prior project records;
- Wisdomux-Link / termux_socket_bridge reference recovered from prior project material;
- dedicated revival branch created.

INFERRED:
- Wisdomux is best positioned as the coordination plane above SelmaOS.

UNVERIFIED:
- original full source tree has not yet been recovered;
- original backend/frontend files have not yet been located;
- original SQLite schema and exact WebSocket protocol remain unrecovered.

BLOCKED:
- none for architecture restoration;
- exact original source recovery depends on locating any surviving files/repository copies.

## Initialize a local database

The schema-only initializer creates a new local SQLite database from the
canonical migrations. It creates no agents, capability grants, tasks, or
network services. The parent directory must already exist, and an existing
target is never modified.

```sh
node wisdomux/bin/initializeDatabase.js \
  --db "$PREFIX/var/lib/selma/coordination.sqlite"
```

Successful output lists the absolute database path and applied migrations as
JSON. Initialization errors go to stderr and return a non-zero exit status.

## Verify maintenance readiness

The preflight command opens an existing coordination database read-only and
checks the canonical schema, SQLite integrity, foreign keys, coordinator
availability, and required capability grants. It does not mutate the database
or start a server.

```sh
node wisdomux/bin/maintenancePreflight.js \
  --db "$PREFIX/var/lib/selma/coordination.sqlite" \
  --coordinator coordinator-1
```

It emits a JSON readiness report. Exit status `0` means ready, `2` means the
report contains blockers, and `1` means the preflight itself could not run.

## Preview maintenance impact

The maintenance preview opens the database read-only and reports the agents
that the cutoff would mark offline plus the project tasks whose stale claims
would be released. It uses the same recovery states, priority ordering, and
sweep limit as maintenance while preserving current truth and approval data.

```sh
node wisdomux/bin/maintenancePreview.js \
  --db "$PREFIX/var/lib/selma/coordination.sqlite" \
  --project wisdomux \
  --coordinator coordinator-1 \
  --cutoff "YYYY-MM-DDTHH:MM:SSZ" \
  --sweep-limit 50
```

The JSON report is explicitly labeled `PREVIEW`. Exit status `0` means the
preview is ready, `2` means it found a blocker, and `1` means it could not run.
In particular, it blocks a cutoff that would mark the coordinator offline
before stale-task recovery could finish.

## Rootless local maintenance

The maintenance command performs one bounded local cycle: it marks agents
whose heartbeat predates the supplied cutoff as offline, then releases their
recoverable task claims. It starts no server and opens no network listener.

Requirements:

- Node.js with the built-in `node:sqlite` module;
- an existing local SQLite database initialized with the Wisdomux migrations;
- a registered coordinator with `agent.monitor` and `task.recover_stale`
  grants.

The command deliberately refuses a missing database instead of silently
creating an empty one.

Direct Node invocation:

```sh
node wisdomux/bin/maintenance.js \
  --db /absolute/path/to/coordination.sqlite \
  --project wisdomux \
  --coordinator coordinator-1 \
  --cutoff "YYYY-MM-DDTHH:MM:SSZ" \
  --sweep-limit 50
```

Termux/rootless launcher:

```sh
chmod +x wisdomux/bin/maintenance-termux.sh
wisdomux/bin/maintenance-termux.sh \
  --db "$PREFIX/var/lib/selma/coordination.sqlite" \
  --project wisdomux \
  --coordinator coordinator-1 \
  --cutoff "YYYY-MM-DDTHH:MM:SSZ"
```

Choose the cutoff deliberately: active agents with an older heartbeat are
marked offline. Successful output is one JSON object listing the normalized
cutoff, expired agents, and recovered tasks. Errors go to stderr and return a
non-zero exit status.

