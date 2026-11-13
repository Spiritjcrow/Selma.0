from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Approval, CapabilityGrant


class SecurityStore:
    """Persistent, transaction-safe local security state."""
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = threading.RLock()
        self._init()

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS grants(
                    grant_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    document TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS grants_subject ON grants(subject);
                CREATE TABLE IF NOT EXISTS approvals(
                    approval_id TEXT PRIMARY KEY,
                    action_hash TEXT NOT NULL,
                    document TEXT NOT NULL,
                    consumed_at TEXT,
                    consumed_action_hash TEXT
                );
                CREATE INDEX IF NOT EXISTS approvals_action ON approvals(action_hash);
                CREATE TABLE IF NOT EXISTS revocations(
                    object_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    revoked_at TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS budget_events(
                    subject TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    event_time REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS budget_idx ON budget_events(subject, rule_id, event_time);
            """)

    def put_grant(self, grant: CapabilityGrant) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO grants(grant_id, subject, document) VALUES(?,?,?)",
                (grant.grant_id, grant.subject, json.dumps(grant.to_dict(), sort_keys=True)),
            )

    def get_grant(self, grant_id: str) -> CapabilityGrant | None:
        with self._db() as db:
            row = db.execute("SELECT document FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
        return CapabilityGrant.from_dict(json.loads(row[0])) if row else None

    def grants_for_subject(self, subject: str) -> list[CapabilityGrant]:
        with self._db() as db:
            rows = db.execute("SELECT document FROM grants WHERE subject=? ORDER BY grant_id", (subject,)).fetchall()
        return [CapabilityGrant.from_dict(json.loads(r[0])) for r in rows]

    def put_approval(self, approval: Approval) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO approvals(approval_id, action_hash, document, consumed_at, consumed_action_hash) VALUES(?,?,?,?,?)",
                (approval.approval_id, approval.action_hash, json.dumps(approval.to_dict(), sort_keys=True), None, None),
            )

    def approvals_for_action(self, action_hash: str) -> list[tuple[Approval, bool]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT document, consumed_at FROM approvals WHERE action_hash=? ORDER BY approval_id",
                (action_hash,),
            ).fetchall()
        return [(Approval.from_dict(json.loads(r[0])), r[1] is not None) for r in rows]

    def consume_approval(self, approval_id: str, action_hash: str, consumed_at: str) -> bool:
        with self._db() as db:
            row = db.execute(
                "SELECT action_hash, consumed_at FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
            if not row or row[0] != action_hash or row[1] is not None:
                return False
            cur = db.execute(
                "UPDATE approvals SET consumed_at=?, consumed_action_hash=? WHERE approval_id=? AND consumed_at IS NULL",
                (consumed_at, action_hash, approval_id),
            )
            return cur.rowcount == 1

    def revoke(self, object_id: str, kind: str, revoked_at: str, reason: str) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO revocations(object_id,kind,revoked_at,reason) VALUES(?,?,?,?)",
                (object_id, kind, revoked_at, reason),
            )

    def is_revoked(self, object_id: str) -> bool:
        with self._db() as db:
            return db.execute("SELECT 1 FROM revocations WHERE object_id=?", (object_id,)).fetchone() is not None

    def revocation_fingerprint(self) -> str:
        from .canonical import canonical_json, sha256_hex
        with self._db() as db:
            rows = db.execute("SELECT object_id,kind,revoked_at,reason FROM revocations ORDER BY object_id").fetchall()
        data = [dict(r) for r in rows]
        return "sha256:" + sha256_hex(canonical_json(data))

    def check_rate(self, subject: str, rule_id: str, now_epoch: float, limit: int, record: bool) -> bool:
        with self._db() as db:
            cutoff = now_epoch - 60.0
            db.execute("DELETE FROM budget_events WHERE event_time < ?", (cutoff,))
            count = db.execute(
                "SELECT COUNT(*) FROM budget_events WHERE subject=? AND rule_id=? AND event_time>=?",
                (subject, rule_id, cutoff),
            ).fetchone()[0]
            if count >= limit:
                return False
            if record:
                db.execute(
                    "INSERT INTO budget_events(subject,rule_id,event_time) VALUES(?,?,?)",
                    (subject, rule_id, now_epoch),
                )
            return True
