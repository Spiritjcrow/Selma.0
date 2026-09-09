from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from .audit import AuditLedger
from .canonical import canonical_json, sha256_hex
from .models import ActionEnvelope, Decision, DecisionReceipt
from .security import WingDingynouse


class SelmaBridgeError(RuntimeError):
    """Raised when Selma-integrated execution cannot safely reach the control plane."""


@dataclass(frozen=True)
class SelmaRoute:
    """Explicit mapping from one FDT effect to one registered Selma tool operation."""

    capability: str
    operation: str
    tool_name: str

    def __post_init__(self) -> None:
        for name in ("capability", "operation", "tool_name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class SelmaToolInvocation:
    """Immutable handoff record supplied to Selma's canonical tool dispatcher.

    FDT may decide that an action is eligible to proceed, but this object is only
    a request to Selma's existing control plane. It is not an authority token and
    cannot bypass Selma permission, replay, audit, cancellation, or kill-switch
    enforcement.
    """

    request_id: str
    actor: str
    on_behalf_of: str | None
    capability: str
    operation: str
    tool_name: str
    resource: str
    method: str
    payload: dict[str, Any]
    provenance: tuple[str, ...]
    action_hash: str
    fdt_policy_build_id: str
    fdt_reason_code: str
    fdt_grant_id: str | None
    fdt_approval_id: str | None
    fdt_receipt_signature: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["provenance"] = list(self.provenance)
        return data


class SelmaControlPlaneBridge:
    """Fail-closed FDT -> Selma handoff with no direct host-effect implementation."""

    def __init__(
        self,
        dispatcher: Callable[[SelmaToolInvocation], Mapping[str, Any]],
        routes: Mapping[str, SelmaRoute],
        *,
        kill_switch_active: Callable[[], bool] | None = None,
    ) -> None:
        if not callable(dispatcher):
            raise TypeError("dispatcher must be callable")
        self._dispatcher = dispatcher
        self._routes = dict(routes)
        if not self._routes:
            raise ValueError("at least one explicit Selma route is required")
        if any(not isinstance(effect, str) or not effect.strip() for effect in self._routes):
            raise ValueError("route effects must be non-empty strings")
        if any(not isinstance(route, SelmaRoute) for route in self._routes.values()):
            raise TypeError("routes must contain SelmaRoute values")
        if kill_switch_active is not None and not callable(kill_switch_active):
            raise TypeError("kill_switch_active must be callable")
        self._kill_switch_active = kill_switch_active

    def execute(self, action: ActionEnvelope, receipt: DecisionReceipt) -> dict[str, Any]:
        if receipt.decision is not Decision.ALLOW:
            raise SelmaBridgeError("FDT decision is not ALLOW")
        if receipt.action_hash != action.action_hash:
            raise SelmaBridgeError("FDT receipt is not bound to this action")
        if self._kill_switch_active is not None and self._kill_switch_active():
            raise SelmaBridgeError("Selma kill switch is active")

        route = self._routes.get(action.effect)
        if route is None:
            raise SelmaBridgeError(f"no explicit Selma route for effect {action.effect}")

        invocation = SelmaToolInvocation(
            request_id=action.action_id,
            actor=action.actor,
            on_behalf_of=action.on_behalf_of,
            capability=route.capability,
            operation=route.operation,
            tool_name=route.tool_name,
            resource=action.resource,
            method=action.method,
            payload=dict(action.payload),
            provenance=tuple(action.provenance),
            action_hash=action.action_hash,
            fdt_policy_build_id=receipt.policy_build_id,
            fdt_reason_code=receipt.reason_code,
            fdt_grant_id=receipt.grant_id,
            fdt_approval_id=receipt.approval_id,
            fdt_receipt_signature=receipt.signature,
        )
        result = self._dispatcher(invocation)
        if not isinstance(result, Mapping):
            raise SelmaBridgeError("Selma dispatcher returned a non-mapping result")
        return dict(result)


class SelmaIntegratedFDTGate:
    """FDT Gate mode that can reach host effects only through Selma's dispatcher.

    Unlike ``FDTGate`` standalone mode, this class has no AdapterRegistry and no
    direct filesystem/network/process execution path. FDT ALLOW is necessary but
    not sufficient: Selma's canonical dispatcher must separately accept and
    report successful execution.
    """

    def __init__(
        self,
        engine: WingDingynouse,
        bridge: SelmaControlPlaneBridge,
        audit: AuditLedger | None = None,
    ) -> None:
        self.engine = engine
        self.bridge = bridge
        self.audit = audit

    def authorize(self, action: ActionEnvelope) -> DecisionReceipt:
        receipt = self.engine.authorize(action, consume_approval=False, record_budget=False)
        if self.audit:
            self.audit.append(
                {"type": "selma_bridge_authorization", "action": action.to_dict(), "receipt": receipt.to_dict()}
            )
        return receipt

    def execute(self, action: ActionEnvelope) -> dict[str, Any]:
        receipt = self.engine.authorize(action, consume_approval=True, record_budget=True)
        if receipt.decision is not Decision.ALLOW:
            if self.audit:
                self.audit.append(
                    {"type": "selma_bridge_blocked", "action": action.to_dict(), "receipt": receipt.to_dict()}
                )
            return {"executed": False, "receipt": receipt.to_dict()}

        try:
            selma_result = self.bridge.execute(action, receipt)
        except SelmaBridgeError as exc:
            if self.audit:
                self.audit.append(
                    {
                        "type": "selma_bridge_denied",
                        "action": action.to_dict(),
                        "receipt": receipt.to_dict(),
                        "reason": str(exc),
                    }
                )
            return {"executed": False, "receipt": receipt.to_dict(), "bridge_error": str(exc)}

        # Gate 1 AdapterResult uses status="success" for a completed effect. Any
        # absent/different status is treated as fail-closed rather than inferred.
        executed = selma_result.get("status") == "success"
        result_hash = "sha256:" + sha256_hex(canonical_json(selma_result))
        if self.audit:
            self.audit.append(
                {
                    "type": "selma_bridge_result",
                    "action": action.to_dict(),
                    "receipt": receipt.to_dict(),
                    "selma_status": selma_result.get("status"),
                    "result_hash": result_hash,
                }
            )
        return {
            "executed": executed,
            "receipt": receipt.to_dict(),
            "selma_result": selma_result,
            "result_hash": result_hash,
        }
