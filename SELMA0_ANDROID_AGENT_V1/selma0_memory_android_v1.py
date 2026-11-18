import json
import os
import re
import sqlite3
import threading
import time

SELMA0_BASE_V1 = os.path.expanduser(os.getenv("SELMA0_BASE_V1", "~/SELMA0_ANDROID_AGENT_V1"))
SELMA0_DATA_V1 = os.path.join(SELMA0_BASE_V1, "selma0_data_android_v1")
SELMA0_DB_V1 = os.path.join(SELMA0_DATA_V1, "selma0_memory_android_v1.sqlite3")

_TOKEN_V1 = re.compile(r"[^\W_]{2,}", re.UNICODE)


def _tokens_v1(text):
    return [token.casefold() for token in _TOKEN_V1.findall(str(text))][:64]


class Selma0MemoryAndroidV1:
    def __init__(self, db_path=SELMA0_DB_V1, enable_fts=True):
        self.db_path = db_path
        self._lock = threading.RLock()
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS selma0_events_v1(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )
        self.fts_enabled = False
        if enable_fts:
            try:
                self.conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS selma0_events_fts_v1 "
                    "USING fts5(content, tokenize='unicode61')"
                )
                self.conn.execute(
                    "INSERT OR IGNORE INTO selma0_events_fts_v1(rowid,content) "
                    "SELECT id,content FROM selma0_events_v1"
                )
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False
        self.conn.commit()

    @property
    def retrieval_mode(self):
        return "sqlite-fts5" if self.fts_enabled else "bounded-lexical-fallback"

    def add(self, role, content, metadata=None):
        metadata = metadata or {}
        with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO selma0_events_v1(ts, role, content, metadata) VALUES(?,?,?,?)",
                (time.time(), str(role), str(content), json.dumps(metadata, separators=(",", ":"))),
            )
            if self.fts_enabled:
                self.conn.execute(
                    "INSERT INTO selma0_events_fts_v1(rowid,content) VALUES(?,?)",
                    (cursor.lastrowid, str(content)),
                )
            self.conn.commit()

    def recent(self, limit=24):
        limit = max(1, min(int(limit), 200))
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts,role,content,metadata FROM selma0_events_v1 ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        rows.reverse()
        return [
            {"ts": row[0], "role": row[1], "content": row[2], "metadata": json.loads(row[3])}
            for row in rows
        ]

    def search(self, query, limit=5, scan_limit=1000):
        tokens = list(dict.fromkeys(_tokens_v1(query)))
        if not tokens:
            return []
        limit = max(1, min(int(limit), 20))
        scan_limit = max(limit, min(int(scan_limit), 5000))
        with self._lock:
            if self.fts_enabled:
                rows = self._search_fts_v1(tokens, limit)
            else:
                rows = self._search_fallback_v1(tokens, limit, scan_limit)
        return [self._result_v1(row) for row in rows]

    def _search_fts_v1(self, tokens, limit):
        expression = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens[:16])
        return self.conn.execute(
            """
            SELECT event.id,event.ts,event.role,event.content,event.metadata,
                   -bm25(selma0_events_fts_v1) AS score
            FROM selma0_events_fts_v1
            JOIN selma0_events_v1 AS event ON event.id=selma0_events_fts_v1.rowid
            WHERE selma0_events_fts_v1 MATCH ?
            ORDER BY bm25(selma0_events_fts_v1), event.id DESC
            LIMIT ?
            """,
            (expression, limit),
        ).fetchall()

    def _search_fallback_v1(self, tokens, limit, scan_limit):
        query_terms = set(tokens)
        rows = self.conn.execute(
            "SELECT id,ts,role,content,metadata FROM selma0_events_v1 ORDER BY id DESC LIMIT ?",
            (scan_limit,),
        ).fetchall()
        ranked = []
        for row in rows:
            document_terms = set(_tokens_v1(row[3]))
            overlap = query_terms.intersection(document_terms)
            if not overlap:
                continue
            coverage = len(overlap) / len(query_terms)
            density = len(overlap) / max(1, len(document_terms))
            score = coverage + (0.25 * density)
            ranked.append((*row, score))
        ranked.sort(key=lambda row: (row[5], row[0]), reverse=True)
        return ranked[:limit]

    @staticmethod
    def _result_v1(row):
        return {
            "id": row[0],
            "ts": row[1],
            "role": row[2],
            "content": row[3],
            "metadata": json.loads(row[4]),
            "score": round(float(row[5]), 6),
        }

    def clear(self):
        with self._lock:
            self.conn.execute("DELETE FROM selma0_events_v1")
            if self.fts_enabled:
                self.conn.execute("DELETE FROM selma0_events_fts_v1")
            self.conn.commit()

    def close(self):
        with self._lock:
            self.conn.close()
