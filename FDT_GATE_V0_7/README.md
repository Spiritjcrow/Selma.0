# Flipp'n Da Table! — FDT Gate v0.7

**Framework-neutral deterministic authorization between AI intent and host execution.**

FDT Gate is the operational security branch of Flipp'n Da Table!. The model/agent may propose an
`ActionEnvelope`; it never grants itself authority. **WingDingynouse HARDSTONE** verifies a signed
policy, a scoped/expiring/revocable capability chain, exact-action approvals for high-impact effects,
resource/rate budgets, and emits a signed decision receipt before any registered host adapter runs.

The unusual FDT Key Grammar remains language identity and expressive syntax — **not a security boundary**.
Canonical atomic forms such as `"jargonsaurousflex" '`×π` and `Table_Sãurāzz'd ållôt..` are preserved
verbatim by the lexer and are not decomposed unless explicitly defined in a future grammar revision.

## Implemented v0.7 slice

- FDTID-1 stable IDs and FDT-IR-1 deterministic policy build IDs
- strict `fdt-policy 0.7` parser/compiler
- Ed25519 signed policy bundles, grants, approvals, and decision receipts
- Genesis-root capability authorization with narrowing checks for delegation
- expiry and immediate persistent revocation
- exact-action, one-time approval binding
- payload and per-minute rate budgets
- SQLite security state
- tamper-evident hash-chained evidence ledger
- framework-neutral Action Envelope model
- two distinct stack adapters that normalize equivalent calls to the same envelope/action hash
- filesystem, HTTPS allowlist, and read-only Git reference adapters
- loopback HTTP middleware with bearer-token-to-principal binding
- fail-closed Selma control-plane bridge for integrated deployments
- parser fuzz/property-style invariants and authorization conformance tests
- offline authorization after dependencies are installed

## Run

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
fdt-gate demo
```

If build dependencies are already installed and the machine must remain offline, use:

```bash
python -m pip install --no-build-isolation -e .
```

Expected demo properties:

- read executes with a valid capability;
- write is blocked pending approval;
- approval is bound to the exact action hash;
- approved write executes once;
- reuse of the one-time approval is blocked;
- evidence ledger verifies.

## Create a local gate

```bash
fdt-gate init ./gate-state
```

The command prints a bearer token once. Private demo keys are stored with restrictive file permissions
where the OS supports them. For production, move Genesis/runtime keys to KMS/HSM/TPM/Android StrongBox.
Normal runtime policy verification loads only the Genesis public key; the Genesis private key is used by
explicit issuance/approval operations.

Start the local middleware:

```bash
fdt-gate serve ./gate-state --bind 127.0.0.1 --port 8767
```

`POST /v1/authorize` evaluates without executing. `POST /v1/execute` re-authorizes at action time,
consumes one-time approvals, and only then reaches an adapter. Both require `Authorization: Bearer <token>`;
the token maps to a trusted principal and the input `actor` must match it.

## Selma/SelmaOS integration

Standalone FDT Gate may use its own bounded reference adapters. **Selma-integrated deployments must not.**
Use `SelmaIntegratedFDTGate` with `SelmaControlPlaneBridge`: an FDT `ALLOW` is handed to Selma as a
fully bound registered-tool request, and Selma's canonical permission, replay, audit, cancellation,
kill-switch, and platform-adapter path remains the final authority for any host effect. Missing routes,
receipt mismatches, kill-switch activation, bridge failures, and Selma denials fail closed.

See `SELMA_INTEGRATION.md` for the contract and wiring model.

## Stable policy subset

```text
fdt-policy 0.7
policy repository-agent
version 0.7.0
default DENY
rule source-read effect=fs.read resource=workspace/** capability=workspace.read decision=ALLOW methods=READ
rule source-write effect=fs.write resource=workspace/** capability=workspace.write decision=REQUIRE_APPROVAL risk=HIGH methods=WRITE
```

Unknown statements/keys, duplicate rule IDs, and invalid resource budgets fail closed.

## Security posture

This release is an **operational reference/pilot runtime**, not a claim of production certification.
It does not claim protection from a compromised OS/kernel/hypervisor, stolen unlocked Genesis private key,
malicious crypto implementation, all side channels, or arbitrary bugs in future third-party adapters.
See `SECURITY.md` and `THREAT_MODEL.md`.
