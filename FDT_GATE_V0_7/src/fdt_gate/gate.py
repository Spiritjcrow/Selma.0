from __future__ import annotations

from typing import Any

from .adapters import AdapterRegistry
from .audit import AuditLedger
from .canonical import canonical_json, sha256_hex
from .models import ActionEnvelope, Decision, DecisionReceipt
from .security import WingDingynouse


class FDTGate:
    def __init__(self, engine: WingDingynouse, adapters: AdapterRegistry | None = None,
                 audit: AuditLedger | None = None):
        self.engine = engine
        self.adapters = adapters or AdapterRegistry()
        self.audit = audit

    def authorize(self, action: ActionEnvelope) -> DecisionReceipt:
        receipt = self.engine.authorize(action, consume_approval=False, record_budget=False)
        if self.audit:
            self.audit.append({"type": "authorization", "action": action.to_dict(), "receipt": receipt.to_dict()})
        return receipt

    def execute(self, action: ActionEnvelope) -> dict[str, Any]:
        receipt = self.engine.authorize(action, consume_approval=True, record_budget=True)
        if receipt.decision != Decision.ALLOW:
            if self.audit:
                self.audit.append({"type": "blocked_execution", "action": action.to_dict(), "receipt": receipt.to_dict()})
            return {"executed": False, "receipt": receipt.to_dict()}

        result = self.adapters.execute(action)
        result_hash = "sha256:" + sha256_hex(canonical_json(result))
        event = {
            "type": "execution", "action": action.to_dict(), "receipt": receipt.to_dict(),
            "result_hash": result_hash,
        }
        if self.audit:
            self.audit.append(event)
        return {"executed": True, "receipt": receipt.to_dict(), "result": result, "result_hash": result_hash}
