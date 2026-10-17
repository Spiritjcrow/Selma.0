"""Private, user-controlled correction ledger, NEVER automatic fine-tuning."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

STATUSES = {"hypothesis", "listener_reported", "rejected"}


def record_correction(database: str | Path, source_sha256: str, start_seconds: float,
                      end_seconds: float, proposed_text: str, status: str,
                      reviewer: str = "human") -> int:
    if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    if not (0 <= start_seconds < end_seconds) or end_seconds - start_seconds > 300:
        raise ValueError("Correction time range must be positive and <=300s")
    if not proposed_text.strip() or not reviewer.strip():
        raise ValueError("Text and reviewer must be non-empty")
    path = Path(database).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_sha256 TEXT NOT NULL,
            start_seconds REAL NOT NULL, end_seconds REAL NOT NULL,
            proposed_text TEXT NOT NULL, status TEXT NOT NULL,
            reviewer TEXT NOT NULL, recorded_utc TEXT NOT NULL
        )""")
        cur = conn.execute("""INSERT INTO corrections
            (source_sha256,start_seconds,end_seconds,proposed_text,status,reviewer,recorded_utc)
            VALUES(?,?,?,?,?,?,?)""", (source_sha256, start_seconds, end_seconds,
            proposed_text, status, reviewer, datetime.now(timezone.utc).isoformat()))
        return int(cur.lastrowid)


def export_corrections(database: str | Path, output_jsonl: str | Path) -> int:
    """Export for human review, not an auto-approved training set."""
    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM corrections ORDER BY id").fetchall()
    with open(output_jsonl, "w", encoding="utf-8") as f:
        for row in rows:
            data = dict(row)
            data["training_approved"] = False
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    return len(rows)