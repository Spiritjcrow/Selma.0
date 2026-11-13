from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .canonical import canonical_json, sha256_hex


class AuditLedger:
    """Append-only hash-chained JSONL evidence log."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def append(self, event: dict) -> dict:
        with self._lock:
            prev = "GENESIS"
            if self.path.exists() and self.path.stat().st_size:
                last = self.path.read_text("utf-8").splitlines()[-1]
                prev = json.loads(last)["record_hash"]
            record = {"prev_hash": prev, "event": event}
            record_hash = "sha256:" + sha256_hex(canonical_json(record))
            record["record_hash"] = record_hash
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                f.flush()
            return record

    def verify(self) -> tuple[bool, int, str | None]:
        prev = "GENESIS"
        if not self.path.exists():
            return True, 0, None
        count = 0
        for idx, line in enumerate(self.path.read_text("utf-8").splitlines(), 1):
            try:
                rec = json.loads(line)
                claimed = rec.pop("record_hash")
                if rec.get("prev_hash") != prev:
                    return False, count, f"line {idx}: previous hash mismatch"
                actual = "sha256:" + sha256_hex(canonical_json(rec))
                if claimed != actual:
                    return False, count, f"line {idx}: record hash mismatch"
                prev = claimed
                count += 1
            except Exception as exc:
                return False, count, f"line {idx}: {exc}"
        return True, count, None
