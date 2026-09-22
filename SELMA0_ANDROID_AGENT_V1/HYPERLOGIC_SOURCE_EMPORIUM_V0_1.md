# Hyperlogic Source Emporium — Procurement Gate v0.1

## Purpose

`Selma0ProcurementGateAndroidV1` is a fail-closed procurement layer that sits before Selma's existing tool registry and permission engine.

Pipeline:

`source -> provenance -> exact pin -> SHA-256 -> capability policy -> verified cache -> activation -> runtime permission -> rollback`

## Security invariants

1. Untrusted source identities never enter the verified cache.
2. Resolved versions must exactly match the requested pin.
3. Artifact bytes must match the expected SHA-256 digest.
4. Requested capabilities must be within procurement policy.
5. Network access defaults to `deny` in the procurement record.
6. Runtime authority is separate from artifact trust and still passes through `Selma0PermissionEngineAndroidV1`.
7. Only verified cached generations can activate.
8. Cache capacity is bounded: admission evicts the least-recently-used inactive generation or fails if every cached generation is active.
9. A cached package/version cannot change artifact or policy; rollback skips an evicted generation if a different record later uses that version.
10. Rollback is limited to configured verified history.
11. Runtime approval must be the literal Boolean `True`; other values cannot authorize a sensitive effect.
12. Procurement, activation, eviction, runtime authorization, and rollback can emit events into `Selma0AuditLogAndroidV1`.

## Current implementation boundary

This v0.1 prototype records an isolation policy but does not itself configure Android sandboxing, Linux namespaces, seccomp, or network namespaces. Source provenance is currently an explicit trusted-source allowlist plus SHA-256 integrity. Publisher signatures, Sigstore/TUF metadata, SBOM verification, transparency-log validation, and APK/system-partition rollback remain future hardening work.

## Regression suite

Run:

```bash
python3 SELMA0_ANDROID_AGENT_V1/tests/test_procurement_gate_v1.py
```

The suite covers trusted procurement, untrusted source rejection, tamper rejection, capability rejection, version drift rejection, bounded cache admission and eviction, immutable generations, rollback identity and history limits, runtime approval gating, and approved sensitive runtime execution.

## Next prototype slice

1. Add signed manifest verification and provenance metadata.
2. Persist verified cache metadata with atomic writes.
3. Add SBOM/dependency graph validation before activation.
4. Enforce network/isolation policy with Android-compatible primitives.
5. Connect activation to the explicit `Selma0ToolRegistryAndroidV1` registration path.
