from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DB = Path(
    os.environ.get(
        "SELMA_MEMORY_DB",
        str(Path(__file__).parent / "data" / "selma_memory_bridge.sqlite3"),
    )
)


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    source: str
    source_record_id: str | None
    role: str | None
    content: str
    created_at: str | None
    imported_at: str
    digest: str
    provenance: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_digest(
    *,
    source: str,
    source_record_id: str | None,
    role: str | None,
    content: str,
    created_at: str | None,
) -> str:
    payload = json.dumps(
        {
            "source": source.strip().lower(),
            "source_record_id": source_record_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class MemoryStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memories (
                    record_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_record_id TEXT,
                    role TEXT,
                    content TEXT NOT NULL,
                    created_at TEXT,
                    imported_at TEXT NOT NULL,
                    digest TEXT NOT NULL UNIQUE,
                    provenance_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_source
                    ON memories(source);
                CREATE INDEX IF NOT EXISTS idx_memories_created_at
                    ON memories(created_at);
                """
            )

    def add(
        self,
        *,
        source: str,
        content: str,
        source_record_id: str | None = None,
        role: str | None = None,
        created_at: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> tuple[MemoryRecord, bool]:
        source = source.strip().lower()
        content = content.strip()
        if not source:
            raise ValueError("source is required")
        if not content:
            raise ValueError("content is required")

        digest = _canonical_digest(
            source=source,
            source_record_id=source_record_id,
            role=role,
            content=content,
            created_at=created_at,
        )
        record = MemoryRecord(
            record_id=str(uuid.uuid4()),
            source=source,
            source_record_id=source_record_id,
            role=role,
            content=content,
            created_at=created_at,
            imported_at=_utc_now(),
            digest=digest,
            provenance=provenance or {},
        )

        with self._connect() as con:
            existing = con.execute(
                "SELECT * FROM memories WHERE digest = ?",
                (digest,),
            ).fetchone()
            if existing:
                return self._from_row(existing), False

            con.execute(
                """
                INSERT INTO memories (
                    record_id, source, source_record_id, role, content,
                    created_at, imported_at, digest, provenance_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.source,
                    record.source_record_id,
                    record.role,
                    record.content,
                    record.created_at,
                    record.imported_at,
                    record.digest,
                    json.dumps(record.provenance, ensure_ascii=False, sort_keys=True),
                ),
            )
        return record, True

    def add_many(self, rows: Iterable[dict[str, Any]]) -> dict[str, int]:
        added = 0
        duplicate = 0
        rejected = 0
        for row in rows:
            try:
                _, created = self.add(**row)
            except (TypeError, ValueError):
                rejected += 1
                continue
            if created:
                added += 1
            else:
                duplicate += 1
        return {"added": added, "duplicate": duplicate, "rejected": rejected}

    def search(
        self,
        query: str,
        *,
        source: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        query = query.strip()
        if not query:
            return []
        limit = max(1, min(int(limit), 50))
        pattern = f"%{query}%"

        sql = """
            SELECT * FROM memories
            WHERE content LIKE ? COLLATE NOCASE
        """
        params: list[Any] = [pattern]
        if source:
            sql += " AND source = ?"
            params.append(source.strip().lower())
        sql += """
            ORDER BY
                CASE WHEN created_at IS NULL THEN 1 ELSE 0 END,
                created_at DESC,
                imported_at DESC
            LIMIT ?
        """
        params.append(limit)

        with self._connect() as con:
            rows = con.execute(sql, params).fetchall()
        return [self._from_row(row) for row in rows]

    def fetch(self, record_id: str) -> MemoryRecord | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM memories WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            record_id=row["record_id"],
            source=row["source"],
            source_record_id=row["source_record_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            imported_at=row["imported_at"],
            digest=row["digest"],
            provenance=json.loads(row["provenance_json"]),
        )

    @staticmethod
    def to_dict(record: MemoryRecord) -> dict[str, Any]:
        return {
            "id": record.record_id,
            "source": record.source,
            "source_record_id": record.source_record_id,
            "role": record.role,
            "content": record.content,
            "created_at": record.created_at,
            "imported_at": record.imported_at,
            "sha256": record.digest,
            "provenance": record.provenance,
        }
