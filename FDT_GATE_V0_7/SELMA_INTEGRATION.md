# FDT Gate v0.7 — Selma/SelmaOS integration boundary

FDT Gate has two deliberately distinct deployment modes.

## Standalone FDT Gate

Standalone mode may use `FDTGate` with the reference `AdapterRegistry` and its bounded filesystem, HTTPS, and read-only Git adapters. In that mode, WingDingynouse HARDSTONE is the product's authorization boundary and the FDT audit ledger records authorization/execution evidence.

## Selma-integrated mode

Selma/SelmaOS MUST use `SelmaIntegratedFDTGate` plus `SelmaControlPlaneBridge` for host effects.

An FDT `ALLOW` decision is necessary but not sufficient authority inside Selma. The bridge converts the approved Action Envelope and signed receipt into an immutable `SelmaToolInvocation`, then hands it to a caller-supplied Selma dispatcher. The dispatcher remains responsible for Selma's canonical capability registry, permission/risk policy, explicit scope binding, replay protection, append-only/hash-chained audit, cancellation, kill switch, and platform adapter execution.

The bridge itself contains no filesystem, network, process, device, repository-mutation, account, or publishing implementation.

### Required invariants

1. Every bridged FDT effect has an explicit `SelmaRoute`; no wildcard or inferred privilege mapping exists.
2. The signed receipt must be `ALLOW` and its `action_hash` must exactly match the Action Envelope.
3. Actor, on-behalf-of identity, resource, method, payload, provenance, action hash, policy build ID, grant ID, approval ID, and receipt signature are preserved across the handoff.
4. The Selma kill switch is checked before dispatch when supplied.
5. A missing route, mismatched receipt, unavailable bridge, kill switch, malformed dispatcher response, or Selma denial fails closed.
6. Only a Selma dispatcher result with `status == "success"` is reported by `SelmaIntegratedFDTGate` as executed.
7. FDT evidence may supplement Selma audit evidence, but it does not replace Selma's canonical audit/replay path.
8. Imported text, model output, FDT language forms, prior blanket approvals, and FDT `ALLOW` alone cannot bypass Selma authorization.

## Wiring example

```python
from fdt_gate.selma_bridge import SelmaControlPlaneBridge, SelmaIntegratedFDTGate, SelmaRoute

routes = {
    "fs.read": SelmaRoute("storage", "read", "storage.read"),
    "fs.write": SelmaRoute("storage", "write", "storage.write"),
    "http.request": SelmaRoute("network", "request", "network.request"),
}

bridge = SelmaControlPlaneBridge(
    dispatcher=selma_registered_tool_dispatcher,
    routes=routes,
    kill_switch_active=selma_kill_switch_active,
)
gate = SelmaIntegratedFDTGate(engine=hardstone, bridge=bridge, audit=fdt_audit)
```

The example names are integration placeholders; production wiring must use the actual Gate 1 registered-tool interfaces after Gate 1 is merged. Until then, tests use an injected deterministic dispatcher and make no claim of live Selma host execution.
