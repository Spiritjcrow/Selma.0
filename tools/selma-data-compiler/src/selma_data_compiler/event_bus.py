from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json, threading, uuid

@dataclass(slots=True)
class SelmaEvent:
    event_id: str
    topic: str
    source: str
    payload: dict
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

class EventBus:
    def __init__(self, ledger_path: Path):
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def publish(self, topic: str, source: str, payload: dict) -> SelmaEvent:
        event = SelmaEvent(uuid.uuid4().hex, topic, source, payload, datetime.now(timezone.utc).isoformat())
        line = json.dumps(event.to_dict(), separators=(",", ":"), sort_keys=True)
        with self._lock:
            with self.ledger_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return event

    def read(self, topic: str | None = None, limit: int = 200) -> list[SelmaEvent]:
        if not self.ledger_path.exists(): return []
        rows = self.ledger_path.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for line in rows[-max(limit * 3, limit):]:
            try:
                ev = SelmaEvent(**json.loads(line))
                if topic is None or ev.topic == topic: out.append(ev)
            except Exception:
                continue
        return out[-limit:]
