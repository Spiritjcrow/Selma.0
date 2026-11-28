# FDT-Omega provenance gate — isolated, non-deployed prototype

**Source**: Nov 11, 2026 SelmaOS/Wisdmux master blueprint. The source names the mechanism `FDT-Omega` and requires Ed25519 signatures at AST/Git/peer propagation boundaries, but ships only SHA-256 digest examples. `FTD-Omega` is treated as a compatibility alias of the documented name; the actual wire spelling remains covered by the digital signature and MUST NOT be silently rewritten before verification.

## Validated capability

- Verify Ed25519 signatures using an explicit `(node_id, key_id) -> public key` trust map. Nothing is trusted by default.
- Enforce exact envelope schema, canonical UTF-8 JSON, key ID, bounded timestamp, short lifetime, signed protocol name, and a durable SQLite nonce table to prevent replay, including after process restart.
- Permit only signed observational messages (`HEALTH_REPORT`, `TELEMETRY_REPORT`, `VECTOR_SYNC_OFFER`, `MUTATION_PROPOSAL`). A signed **proposal is not permission to execute**.
- Fail-closed for invalid or untrusted signatures, unknown wire protocol, and forbidden operational actions. The module returns `freeze_node=True` to an embedding runtime but **does not itself pause a live mesh**. That requires explicit integration, test, and deployment.
- Expired/future messages are rejected, but do not themselves freeze a node (to avoid an unnecessary whole-mesh outage on routine clock drift).

## Deliberate non-capabilities

- No wallet, payment, billing, crypto transfer, private key, exchange order, or financial settlement endpoints.
- No network access or automatic mutation, self-healing deployment, remote device control, or peer-to-peer listener.
- No production node discovery, certificate/key rotation protocol, revocation checks, signed trust store update, multi-node quorum, or peer authentication transport is claimed.
- No production-ready canonical JSON standard (RFC 8785) is claimed. This is a Python-only schema with deterministic JSON; cross-language interoperability needs a published canonicalization specification before real peers use it.
- No claims of real-time autonomous supervision or cloud cluster synchronization.

## Integration stop gates

1. Keep Selma.0 issue #43 authenticated local API/approval remediation as P0; neither signed payloads nor the tokenized transport alone authorizes an action.
2. Test key management, revocation, and per-node trust policies; deliver real Ed25519 public key enrollment through a separate authenticated operator path.
3. Add append-only audit output, bounded queue, genuine heartbeat monitoring, defined p95/p99 latency SLOs, and privacy redaction before production operation.
4. Restrict self-healing to reversible transport retries with exponential backoff; do not silently mutate protocol, grant rights, rotate keys, merge/deploy, or settle payments.
5. Run platform-specific tests on actual Termux/Android and remote peers and establish an independent rollback strategy.
6. Test tamper/replay and signature failures including key replacement and database restore before making `freeze_node` affect a live service.

## Reproduce local checks

```bash
python -m pip install 'cryptography>=46,<47'
python -m unittest discover -s tests -v
```

**Release status:** branch-only test candidate; not wired into a live node. Updating existing main or external peers requires separate review, feature flag, staged rollout, and authorized production integration.