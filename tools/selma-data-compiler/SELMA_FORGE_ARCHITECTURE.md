# Selma Forge / Selmatizer Architecture

This layer turns the data compiler into a project-wide coordination system.

## Operating principle

**Attempt first, ask minimally, preserve evidence.**

When an action cannot be executed directly, the fallback order is:

1. execute a legitimately available capability;
2. run a safe local simulation/sandbox verification;
3. produce a concrete implementation or handoff;
4. record the exact blocker and safest alternative.

The system must never claim root/sudo access, device control, remote connectivity, test success, or deployment success unless that state was actually observed.

## Core stages

1. Collect
2. Compile
3. Classify
4. Deduplicate
5. Map
6. Reconcile
7. Delegate
8. Plan upgrades
9. Sandbox verify
10. Stabilize
11. Publish evidence

## Super-user / capability model

Selma may use legitimate elevated privileges where the host grants them, but it must not bypass authentication, operating-system protections, or hard safety controls.

Capability decisions are one of: `execute`, `simulate`, `propose`, `blocked`.

This makes the assistant super-user-ready without fabricating privileges.

## Collaboration

`events.jsonl` is an append-only local event ledger. Agent roles coordinate through topics without overwriting each other's state.

## Delegation roles

- core-architect
- agent-orchestrator
- memory-rag-engineer
- voice-runtime-engineer
- avatar-ui-engineer
- device-integration-engineer
- network-integration-engineer
- connector-engineer
- automation-engineer
- runtime-reliability-engineer
- sandbox-researcher
- capability-policy-reviewer
- configuration-curator
- verification-engineer
- project-archivist
- build-release-engineer
- product-ui-engineer
- triage-architect

## Encryption

Integrity uses SHA-256. HMAC signing is built in. Optional AES-256-GCM envelope encryption is available with the `crypto` extra. Encryption keys remain caller-owned and are not written into project files by the compiler.
