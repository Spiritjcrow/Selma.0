from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
import json
from .compiler import SelmaDataCompiler
from .delegation import delegate_needs
from .event_bus import EventBus
from .policy import CapabilityBroker
from .sandbox import VirtualSandbox

@dataclass(slots=True)
class ForgeSnapshot:
    created_at: str
    workspace: str
    compiler_output: str
    task_count: int
    conflict_count: int
    need_count: int
    policy: dict
    phases: list[str]
    def to_dict(self) -> dict: return asdict(self)

class SelmaForge:
    PHASES = ["collect","compile","classify","deduplicate","map","reconcile","delegate","plan-upgrades","sandbox-verify","stabilize","publish-evidence"]

    def __init__(self, workspace: Path, output_dir: Path | None = None):
        self.workspace = workspace.expanduser().resolve()
        self.output_dir = output_dir or (self.workspace / ".selma" / "forge")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.bus = EventBus(self.output_dir / "events.jsonl")
        self.policy = CapabilityBroker(minimal_questions=True, max_questions=1)
        self.sandbox = VirtualSandbox()

    def run(self, roots: list[str | Path] | None = None) -> dict:
        roots = roots or [self.workspace]
        self.bus.publish("forge.start", "selma-forge", {"roots": [str(r) for r in roots]})
        compile_out = self.output_dir / "compiler"
        result = SelmaDataCompiler(compile_out).compile(roots)
        tasks = [t.to_dict() for t in delegate_needs(result["needs"])]
        (self.output_dir / "delegated_tasks.json").write_text(json.dumps(tasks, indent=2), encoding="utf-8")
        upgrade_plan = [{"task_id":t["task_id"],"role":t["role"],"objective":t["objective"],"execution_mode":"propose-or-sandbox-first","completion_evidence":t["evidence_required"]} for t in tasks]
        (self.output_dir / "upgrade_plan.json").write_text(json.dumps(upgrade_plan, indent=2), encoding="utf-8")
        snapshot = ForgeSnapshot(datetime.now(timezone.utc).isoformat(), str(self.workspace), str(compile_out), len(tasks), len(result["conflicts"]), len(result["needs"]), self.policy.policy_snapshot(), self.PHASES)
        (self.output_dir / "forge_snapshot.json").write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
        self.bus.publish("forge.complete", "selma-forge", snapshot.to_dict())
        return {"snapshot": snapshot.to_dict(), "tasks": tasks, "upgrade_plan": upgrade_plan, "compiler": result}
