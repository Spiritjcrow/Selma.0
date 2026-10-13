import json
import os
import sqlite3
import stat
import time

SELMA0_BASE_V1 = os.path.expanduser(os.getenv("SELMA0_BASE_V1", "~/SELMA0_ANDROID_AGENT_V1"))
SELMA0_DATA_V1 = os.path.join(SELMA0_BASE_V1, "selma0_data_android_v1")
SELMA0_DB_V1 = os.path.join(SELMA0_DATA_V1, "selma0_memory_android_v1.sqlite3")


def _prepare_private_store_v1(path):
    """Refuse symlinked store paths; limit new and existing store access."""
    path = os.path.abspath(os.path.expanduser(path))
    directory = os.path.dirname(path)
    cursor = directory
    while True:
        if os.path.islink(cursor):
            raise PermissionError("symlinked memory directory rejected")
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    if os.path.lexists(path):
        mode = os.lstat(path).st_mode
        if not stat.S_ISREG(mode):
            raise PermissionError("memory path must be a regular file")
        os.chmod(path, 0o600)
    return path


class Selma0MemoryAndroidV1:
    def __init__(self, db_path=SELMA0_DB_V1):
        self.db_path = _prepare_private_store_v1(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        os.chmod(self.db_path, 0o600)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA secure_delete=ON")
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
