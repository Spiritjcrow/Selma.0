from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib

ROLE_MAP = {"core":"core-architect","agents":"agent-orchestrator","memory":"memory-rag-engineer","voice":"voice-runtime-engineer","avatar":"avatar-ui-engineer","devices":"device-integration-engineer","network":"network-integration-engineer","adapters":"connector-engineer","automations":"automation-engineer","runtime":"runtime-reliability-engineer","experiments":"sandbox-researcher","local-sandbox":"sandbox-researcher","safety":"capability-policy-reviewer","config":"configuration-curator","tests":"verification-engineer","docs":"project-archivist","build":"build-release-engineer","ui":"product-ui-engineer","unknown":"triage-architect"}

@dataclass(slots=True)
class DelegatedTask:
    task_id: str
    domain: str
    role: str
    objective: str
    priority: int
    evidence_required: list[str]
    status: str = "queued"

    def to_dict(self) -> dict:
        return asdict(self)

def delegate_need(need: dict) -> DelegatedTask:
    domain = need.get("domain", "unknown")
    role = ROLE_MAP.get(domain, ROLE_MAP["unknown"])
    objective = f'Resolve {need.get("status", "need")}: {need.get("requirement", "unspecified")}'
    raw = f"{domain}|{role}|{objective}"
    priority = 100 if need.get("status") == "missing-integration-domain" else 70
    return DelegatedTask(hashlib.sha256(raw.encode()).hexdigest()[:18], domain, role, objective, priority, ["source-change-or-explicit-resolution", "verification-result", "provenance"])

def delegate_needs(needs: list[dict]) -> list[DelegatedTask]:
    return sorted([delegate_need(n) for n in needs], key=lambda t: (-t.priority, t.domain, t.task_id))
