# Selma Sol Security Fabric v1

Status: architecture contract / non-destructive foundation

## Purpose

Selma Sol Blue and Selma Sol Red share one authorization-aware control plane for
networking, servers, remote storage, repositories, mirrors, and future KAI agent
layers without granting blanket or self-expanding privilege.

The fabric is transport-agnostic and provider-agnostic. It must continue to work
when Wi-Fi, carrier, IP address, repository host, storage provider, or device
changes.

## Operating modes

### Sol Blue
Defensive observation and verification mode.

Allowed by default:
- inventory configured resources;
- read health/status/metadata;
- compare mirrors;
- verify hashes/signatures;
- collect logs and provenance;
- run non-destructive diagnostics;
- build recovery plans and dry-run changes.

Not allowed by default:
- credential rotation;
- account-security changes;
- destructive mutation;
- public exposure;
- permission escalation;
- bypass of provider or OS controls.

### Sol Red
Controlled defensive response mode.

Sol Red may perform mutations only when a capability grant explicitly authorizes
the target, action class, scope, expiry, and approval policy. High-impact actions
remain human-gated.

Sol Red never means unrestricted root, universal admin, or authority to bypass
provider security controls.

## Human authority contract

KAI/Selma operates under human-controlled policy.

Every action request is normalized into:

```text
principal
intent
target
action
scope
risk_class
required_capability
approval_state
deadline
rollback_plan
evidence_requirements
```

Human prompts may arrive through text, voice, gesture, or other approved local
input methods. Input modality does not increase privilege. All modalities resolve
to the same signed/recorded intent object before execution.

No agent may mint its own higher privilege, broaden its own scope, disable audit,
or silently convert a read capability into a write capability.

## Capability grants

A capability grant is narrow, time-bound, revocable, and target-bound.

Example conceptual shape:

```json
{
  "principal": "selma.sol-red",
  "target": "github:Spiritjcrow/Selma.0",
  "actions": ["read", "branch-write"],
  "scope": ["feature/*"],
  "expires_at": "2026-10-08T00:00:00Z",
  "requires_human_approval": ["merge", "release", "secret-rotation"]
}
```

Credentials are references to a secret broker, never embedded in policy or logs.

## Resource registry

All infrastructure is represented through a canonical registry instead of
hard-coded endpoints.

Resource classes:
- local device/runtime;
- LAN/WAN interface;
- remote server/VM/container;
- object/file storage;
- source repository;
- repository mirror;
- CI/CD provider;
- package/artifact registry;
- database;
- messaging/queue;
- observability/logging endpoint.

Each entry records:
- stable resource ID;
- provider/type;
- endpoint;
- trust state;
- ownership/authorization class;
- credential reference;
- supported operations;
- connectivity state;
- last verified time;
- provenance;
- mirror relationships;
- recovery priority.

## Mirror fabric

"Every mirror" means every configured and authorized mirror in the registry, not
arbitrary systems on the Internet.

Mirror groups can contain GitHub, GitLab, local bare Git, object storage, NAS,
Drive-like storage, or future providers.

Required mirror behavior:
1. identify canonical source;
2. fetch metadata;
3. compare refs/manifests;
4. verify content hashes;
5. classify divergence;
6. generate a synchronization plan;
7. require capability authorization before mutation;
8. preserve provenance and rollback references.

Conflicts fail closed. No forced overwrite is automatic.

## Network abstraction

Never anchor SelmaOS to one SSID, ISP, router, IP, or carrier.

Transport state is modeled independently from services:
- offline/local;
- Wi-Fi;
- Ethernet;
- cellular;
- VPN/tunnel;
- other approved transports.

The runtime selects the best available route while preserving service policy,
loopback-only restrictions, and explicit public-exposure rules.

## Provider adapters

Adapters implement a common contract:

```text
discover()
health()
read()
plan_change()
apply_change(capability_grant)
verify()
rollback()
```

Initial adapter families:
- GitHub;
- GitLab;
- local Git;
- generic SSH/SFTP where explicitly authorized;
- object storage;
- Google Drive / Dropbox style storage through approved connectors;
- local filesystem;
- CI providers;
- generic HTTPS APIs with explicit credentials.

Adapters must never treat a missing permission as permission to improvise a
bypass.

## Decision engine / NeuralGates

"NeuralGates" is the deterministic policy boundary between reasoning and action.

Pipeline:
1. observe;
2. classify evidence;
3. propose action;
4. evaluate capability;
5. evaluate risk;
6. require human approval where policy says so;
7. execute one bounded action;
8. verify result;
9. append tamper-evident audit record;
10. continue or stop.

AI inference may propose. Policy decides whether execution is permitted.

## Truth-state model

Every result is labeled:
- REAL: directly verified;
- PREVIEW: planned/dry-run/generated proposal;
- INFERRED: reasoned from evidence;
- UNVERIFIED: not yet evidenced;
- BLOCKED: prevented by permission, dependency, or platform state.

No layer may promote a state without new evidence.

## Offline and continuity behavior

When remote services are unavailable:
- preserve local queue;
- continue local diagnostics;
- retain signed intents;
- avoid retry storms;
- never weaken security to regain connectivity;
- replay only still-valid, authorized operations after reconnection;
- revalidate target state before mutation.

## High-impact gates

Always require explicit human approval at execution time for:
- publishing/releasing;
- merging protected branches;
- deleting remote data;
- changing account security;
- rotating/revoking credentials;
- widening repository/server permissions;
- exposing a service publicly;
- purchasing resources;
- bypassing OS, MDM, carrier, or provider restrictions.

## KAI integration

KAI can consume the same resource graph, capability broker, mirror registry,
decision journal, and truth-state ledger.

KAI may reason across infrastructure globally but execution remains bounded by
the same human authority and capability system. "Synthetic consciousness" is a
product architecture term here, not a claim that the software is biologically or
independently conscious.

## Next implementation slice

1. Define typed resource/capability models.
2. Add read-only Sol Blue registry and health probes.
3. Add mirror diff planner.
4. Add dry-run Sol Red action planner.
5. Add tamper-evident decision journal.
6. Add provider adapters incrementally.
7. Add approval broker for consequential actions.
8. Add offline queue with revalidation-before-replay.
