"""Local evidence ledger. This prototype never executes repo commands or GitHub writes.

SHA-256 audit linking detects accidental changes but is not a tamper-proof security
boundary against a database administrator. Store the DB in a protected directory.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

CHOICES = {
    "A": "APPROVE_READ_ONLY_REVIEW",
    "B": "HOLD",
    "C": "REQUEST_EVIDENCE",
    "D": "REJECT",
}
CRITICAL_ISSUES = {("Spiritjcrow/Selma.0", n) for n in (26, 43, 44, 75)}
HIGH_ISSUES = {("Spiritjcrow/Selma.0", n) for n in (15, 17, 39, 49, 51, 62, 81, 83, 85, 88, 96)} | {("Spiritjcrow/Dungeons-Crows", 7), ("Spiritjcrow/CrowRF", 2)}

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def stable_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def priority(repository, kind, number):
    if kind == "issue" and (repository, int(number)) in CRITICAL_ISSUES:
        return "P0"
    if kind == "issue" and (repository, int(number)) in HIGH_ISSUES:
        return "P1"
    return "P2"

class Registry:
    def __init__(self, filename):
        self.filename = Path(filename)
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.filename))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS items (
          item_key TEXT PRIMARY KEY, repository TEXT NOT NULL, kind TEXT NOT NULL,
          number INTEGER NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
          updated_at TEXT, head_sha TEXT, provenance TEXT NOT NULL,
          priority TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
          decision TEXT, decision_digest TEXT, decision_at TEXT,
          UNIQUE(repository,kind,number)
        );
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
          type TEXT NOT NULL, item_key TEXT NOT NULL,
          details TEXT NOT NULL, prior_hash TEXT NOT NULL, event_hash TEXT NOT NULL
        );
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _append_event(self, typ, key, details):
        prev = self.db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev[0] if prev else "0" * 64
        data = stable_json({"type": typ, "item_key": key, "details": details})
        digest = hashlib.sha256((prev_hash + data).encode("utf8")).hexdigest()
        self.db.execute("INSERT INTO events(occurred_at,type,item_key,details,prior_hash,event_hash) VALUES(?,?,?,?,?,?)",
                        (utcnow(), typ, key, data, prev_hash, digest))

    def import_item(self, record, provenance="github_rest"):
        required = ("repository", "kind", "number", "title", "url")
        missing = [k for k in required if not record.get(k)]
        if missing: raise ValueError("Missing required fields: " + ", ".join(missing))
        repo, kind, n = record["repository"], record["kind"], int(record["number"])
        if kind not in ("issue", "pr") or n < 1: raise ValueError("Invalid kind or number")
        if not isinstance(repo,str) or "/" not in repo: raise ValueError("Invalid repository")
        if not str(record["url"]).startswith("https://github.com/" + repo + "/"):
            raise ValueError("URL/repository mismatch")
        key = f"{repo}:{kind}:{n}"
        title = str(record["title"])[:1000]
        updated_at = record.get("updated_at")
        sha = record.get("head_sha")
        observed = {"title":title,"url":record["url"],"updated_at":updated_at,"head_sha":sha}
        fingerprint = hashlib.sha256(stable_json(observed).encode()).hexdigest()
        now = utcnow()
        old = self.db.execute("SELECT * FROM items WHERE item_key=?", (key,)).fetchone()
        if old is None:
            self.db.execute("""INSERT INTO items(item_key,repository,kind,number,title,url,updated_at,head_sha,provenance,priority,first_seen,last_seen)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(key,repo,kind,n,title,record["url"],updated_at,sha,provenance,priority(repo,kind,n),now,now))
            self._append_event("DISCOVERED",key,{"fingerprint":fingerprint})
            result = "added"
        else:
            old_fp = hashlib.sha256(stable_json({"title":old["title"],"url":old["url"],"updated_at":old["updated_at"],"head_sha":old["head_sha"]}).encode()).hexdigest()
            changed = old_fp != fingerprint
            # Any changed source invalidates a decision. It does not automatically grant authority.
            self.db.execute("""UPDATE items SET title=?,url=?,updated_at=?,head_sha=?,provenance=?,last_seen=?,
                            decision=CASE WHEN ? THEN NULL ELSE decision END,
                            decision_digest=CASE WHEN ? THEN NULL ELSE decision_digest END,
                            decision_at=CASE WHEN ? THEN NULL ELSE decision_at END WHERE item_key=?""",
                            (title,record["url"],updated_at,sha,provenance,now,changed,changed,changed,key))
            if changed:self._append_event("SOURCE_CHANGED",key,{"old":old_fp,"new":fingerprint,"approval_invalidated":True})
            result = "updated" if changed else "unchanged"
        self.db.commit()
        return key,result

    def decide(self, key, choice):
        choice=choice.upper().strip()
        if choice not in CHOICES:raise ValueError("Choice must be A, B, C, or D")
        old=self.db.execute("SELECT * FROM items WHERE item_key=?",(key,)).fetchone()
        if old is None:raise ValueError("Unknown item")
        # Approval is for inventory review only, never shell execution or side effects.
        payload={"title":old["title"],"url":old["url"],"updated_at":old["updated_at"],"head_sha":old["head_sha"]}
        digest=hashlib.sha256(stable_json(payload).encode()).hexdigest()
        self.db.execute("UPDATE items SET decision=?,decision_digest=?,decision_at=? WHERE item_key=?",(CHOICES[choice],digest,utcnow(),key))
        self._append_event("OWNER_DECISION",key,{"choice":choice,"scope":"read_only_review","fingerprint":digest})
        self.db.commit()
        return CHOICES[choice]

    def list_items(self):
        return [dict(r) for r in self.db.execute("""SELECT * FROM items ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END, repository, kind, number""")]

    def verify_chain(self):
        prior="0"*64
        for r in self.db.execute("SELECT * FROM events ORDER BY seq"):
            expected=hashlib.sha256((prior+r["details"]).encode()).hexdigest()
            if r["prior_hash"]!=prior or r["event_hash"]!=expected:return False
            prior=expected
        return True