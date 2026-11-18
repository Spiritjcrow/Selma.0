from __future__ import annotations
import json, sqlite3
from pathlib import Path
from .model import Artifact, Conflict, Need

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS artifacts (artifact_id TEXT PRIMARY KEY, path TEXT NOT NULL, root TEXT NOT NULL, relative_path TEXT NOT NULL, name TEXT NOT NULL, suffix TEXT, size INTEGER NOT NULL, sha256 TEXT NOT NULL, modified_ns INTEGER NOT NULL, domain TEXT NOT NULL, kind TEXT NOT NULL, evidence_state TEXT NOT NULL, authority INTEGER NOT NULL, confidence REAL NOT NULL, mapping_reason TEXT NOT NULL, symbols_json TEXT NOT NULL, references_json TEXT NOT NULL, metadata_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_artifacts_domain ON artifacts(domain);
CREATE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256);
CREATE INDEX IF NOT EXISTS idx_artifacts_name ON artifacts(name);
CREATE TABLE IF NOT EXISTS conflicts (conflict_key TEXT PRIMARY KEY, reason TEXT NOT NULL, artifact_ids_json TEXT NOT NULL, paths_json TEXT NOT NULL, resolution TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS needs (need_id TEXT PRIMARY KEY, domain TEXT NOT NULL, requirement TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, candidates_json TEXT NOT NULL);
"""

def write_catalog(path: Path, artifacts: list[Artifact], conflicts: list[Conflict], needs: list[Need]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        con.execute("DELETE FROM artifacts"); con.execute("DELETE FROM conflicts"); con.execute("DELETE FROM needs")
        con.executemany("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [(a.artifact_id, a.path, a.root, a.relative_path, a.name, a.suffix, a.size, a.sha256, a.modified_ns, a.domain, a.kind, a.evidence_state, a.authority, a.confidence, a.mapping_reason, json.dumps(a.symbols), json.dumps(a.references), json.dumps(a.metadata)) for a in artifacts])
        con.executemany("INSERT INTO conflicts VALUES (?,?,?,?,?)", [(c.conflict_key, c.reason, json.dumps(c.artifact_ids), json.dumps(c.paths), c.resolution) for c in conflicts])
        con.executemany("INSERT INTO needs VALUES (?,?,?,?,?,?)", [(n.need_id, n.domain, n.requirement, n.status, n.reason, json.dumps(n.candidates)) for n in needs])
        con.commit()
    finally:
        con.close()
