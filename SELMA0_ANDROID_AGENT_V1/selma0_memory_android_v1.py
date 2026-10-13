import json
import os
import sqlite3
import time

from selma0_private_storage_v1 import private_directory, private_file

SELMA0_BASE_V1 = os.path.expanduser(os.getenv("SELMA0_BASE_V1", "~/SELMA0_ANDROID_AGENT_V1"))
SELMA0_DATA_V1 = os.path.join(SELMA0_BASE_V1, "selma0_data_android_v1")
SELMA0_DB_V1 = os.path.join(SELMA0_DATA_V1, "selma0_memory_android_v1.sqlite3")
private_directory(SELMA0_DATA_V1)


class Selma0MemoryAndroidV1:
    def __init__(self, db_path=SELMA0_DB_V1):
        self.db_path = os.path.abspath(os.path.expanduser(db_path))
        private_directory(os.path.dirname(self.db_path))
        private_file(self.db_path)
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
        self.conn.commit()

    def add(self, role, content, metadata=None):
        metadata = metadata or {}
        self.conn.execute(
            "INSERT INTO selma0_events_v1(ts, role, content, metadata) VALUES(?,?,?,?)",
            (time.time(), str(role), str(content), json.dumps(metadata, separators=(",", ":"))),
        )
        self.conn.commit()

    def recent(self, limit=24):
        limit = max(1, min(int(limit), 200))
        rows = self.conn.execute(
            "SELECT ts,role,content,metadata FROM selma0_events_v1 ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        rows.reverse()
        return [
            {"ts": r[0], "role": r[1], "content": r[2], "metadata": json.loads(r[3])}
            for r in rows
        ]

    def clear(self):
        self.conn.execute("DELETE FROM selma0_events_v1")
        self.conn.commit()
