#!/usr/bin/env python3
"""Tesarac: local, bounded, tamper-evident diagnostic checkpoints (not notarization)."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

VERSION = 1
ZERO = "0" * 64
MAX_LEDGER_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 512 * 1024
MAX_PARTS = 1024
ALLOWED_KINDS = {"note", "logcat", "interfaces", "partition"}

class EvidenceError(ValueError):
    pass

def strict_json(raw: str):
    def unique_pairs(pairs):
        value = {}
        for k, v in pairs:
            if k in value:
                raise EvidenceError("duplicate JSON key")
            value[k] = v
        return value
    def reject_constant(value):
        raise EvidenceError("non-finite JSON constant: " + value)
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)

def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def valid_digest(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None

def verify_bytes(blob: bytes, expected_sha: str | None = None, expected_count: int | None = None):
    if len(blob) > MAX_LEDGER_BYTES:
        raise EvidenceError("ledger exceeds bounded size")
    if not blob:
        raise EvidenceError("no session recorded")
    if not blob.endswith(b"\n"):
        raise EvidenceError("incomplete final record")
    head = ZERO
    session = None
    count = 0
    for raw in blob.splitlines():
        if len(raw) > MAX_RECORD_BYTES:
            raise EvidenceError("record exceeds bounded size")
        try:
            event = strict_json(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise EvidenceError("malformed JSON line") from exc
        if not isinstance(event, dict) or set(event) != {"v", "session", "seq", "utc", "kind", "prev", "payload", "sha256"}:
            raise EvidenceError("event schema mismatch")
        if event["v"] != VERSION or type(event["seq"]) is not int or event["seq"] != count:
            raise EvidenceError("invalid version or sequence")
        if not isinstance(event["session"], str) or not event["session"]:
            raise EvidenceError("invalid session")
        if count == 0:
            if event["kind"] != "session.start":
                raise EvidenceError("missing session start")
            session = event["session"]
        elif event["session"] != session or event["kind"] == "session.start":
            raise EvidenceError("session mismatch")
        if not isinstance(event["utc"], str) or not isinstance(event["kind"], str):
            raise EvidenceError("invalid event metadata")
        if not isinstance(event["payload"], dict) or event["prev"] != head:
            raise EvidenceError("payload / predecessor mismatch")
        digest = event.pop("sha256")
        if not valid_digest(digest) or digest != sha(canonical(event)):
            raise EvidenceError("event integrity mismatch")
        head = digest
        count += 1
    if expected_sha is not None and head != expected_sha:
        raise EvidenceError("head digest differs from external anchor")
    if expected_count is not None and count != expected_count:
        raise EvidenceError("event count differs from external anchor")
    return {"session": session, "records": count, "head_sha256": head, "verdict": "PASS"}

@contextmanager
def locked_ledger(path: Path):
    """fcntl locks supported on Android/Linux/macOS; fail closed on other OSes."""
    try:
        import fcntl
    except ImportError as exc:
        raise EvidenceError("file locking unavailable on this OS") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

def read_ledger(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""

def append_event(path: Path, kind: str, payload: dict) -> dict:
    if not isinstance(payload, dict) or not isinstance(kind, str):
        raise EvidenceError("invalid event inputs")
    with locked_ledger(path):
        blob = read_ledger(path)
        if blob:
            base = verify_bytes(blob)
            if kind == "session.start":
                raise EvidenceError("session already exists")
            session, count, prev = base["session"], base["records"], base["head_sha256"]
        else:
            if kind != "session.start":
                raise EvidenceError("initialize session first")
            session, count, prev = str(uuid.uuid4()), 0, ZERO
        event = {"v": VERSION, "session": session, "seq": count, "utc": utc_now(), "kind": kind, "prev": prev, "payload": payload}
        digest = sha(canonical(event))
        event["sha256"] = digest
        encoded = canonical(event) + b"\n"
        if len(encoded) > MAX_RECORD_BYTES or len(blob) + len(encoded) > MAX_LEDGER_BYTES:
            raise EvidenceError("ledger size limit reached")
        with path.open("ab") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        return {"session": session, "seq": count, "kind": kind, "head_sha256": digest}

def init(path: Path):
    return append_event(path, "session.start", {"mode": "local", "certified_notary": False, "algorithm": "sha256-chain-v1"})

def note(path: Path, text: str, issue: str = ""):
    if not text or len(text.encode("utf-8")) > 8192:
        raise EvidenceError("note must be 1..8192 bytes")
    if issue and not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/(issues|pull)/\d+", issue):
        raise EvidenceError("issue / PR must be a GitHub issue or PR URL")
    return append_event(path, "note", {"text": text, "artifact": issue or None, "verdict": "NOT_RUN"})

def probe(kind: str) -> dict:
    if kind not in {"logcat", "interfaces"}:
        raise EvidenceError("unsupported probe")
    if kind == "logcat":
        options = [("logcat", ["logcat", "-d", "-t", "250"])]
    else:
        options = [("ifconfig", ["ifconfig", "-a"]), ("ip", ["ip", "-br", "addr"])]
    command = None
    for name, argv in options:
        if shutil.which(name):
            command = argv
            break
    if not command:
        return {"verdict": "BLOCKED", "reason": "required tool not installed", "probe": kind}
    started = time.monotonic_ns()
    try:
        out = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"verdict": "BLOCKED", "reason": "tool unavailable or timed out", "probe": kind}
    elapsed = round((time.monotonic_ns() - started) / 1_000_000, 3)
    if out.returncode != 0:
        return {"verdict": "BLOCKED", "reason": "tool returned nonzero", "probe": kind, "exit_code": out.returncode, "latency_ms": elapsed}
    return {"verdict": "PASS", "probe": kind, "tool": command[0], "latency_ms": elapsed,
            "output_bytes": len(out.stdout), "output_sha256": sha(out.stdout),
            "output_lines": len(out.stdout.splitlines())}

def partition(path: Path, chunk_bytes: int = 65536) -> dict:
    if not 1024 <= chunk_bytes <= 1024 * 1024:
        raise EvidenceError("chunk_bytes must be 1024..1048576")
    if not path.is_file() or path.is_symlink():
        return {"verdict": "BLOCKED", "reason": "input must be an existing regular non-symlink file"}
    size = path.stat().st_size
    if size > chunk_bytes * MAX_PARTS:
        return {"verdict": "BLOCKED", "reason": "too many bounded partitions"}
    began = time.monotonic_ns()
    parts = []
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            part = f.read(chunk_bytes)
            if not part:
                break
            start = len(parts) * chunk_bytes
            parts.append({"start": start, "end_exclusive": start + len(part), "sha256": sha(part)})
            h.update(part)
        if f.tell() != size or path.stat().st_size != size:
            return {"verdict": "BLOCKED", "reason": "source size changed while reading"}
    return {"verdict": "PASS", "name": path.name, "size_bytes": size, "chunk_bytes": chunk_bytes,
            "parts": parts, "file_sha256": h.hexdigest(),
            "latency_ms": round((time.monotonic_ns() - began) / 1_000_000, 3)}

def run_unit(unit: dict) -> dict:
    kind = unit["kind"]
    if kind == "note":
        segments = unit.get("segments", [])
        if not isinstance(segments, list) or not segments or any(not isinstance(x, str) or len(x) > 8192 for x in segments):
            raise EvidenceError("note requires segments: list of strings")
        sep = unit.get("separator", "")
        if not isinstance(sep, str) or len(sep) > 128:
            raise EvidenceError("invalid separator")
        text = sep.join(segments)
        if len(text.encode("utf-8")) > 8192:
            raise EvidenceError("assembled note too large")
        return {"verdict": "NOT_RUN", "text": text, "segment_count": len(segments)}
    if kind in {"logcat", "interfaces"}:
        return probe(kind)
    if kind == "partition":
        filepath = unit.get("path")
        if not isinstance(filepath, str) or not filepath:
            raise EvidenceError("partition requires path")
        return partition(Path(filepath), unit.get("chunk_bytes", 65536))
    raise EvidenceError("unsupported unit kind")

def check_plan(plan: dict) -> list[dict]:
    if not isinstance(plan, dict) or set(plan) != {"version", "units"} or plan["version"] != VERSION:
        raise EvidenceError("mosaic schema / version mismatch")
    units = plan["units"]
    if not isinstance(units, list) or not 1 <= len(units) <= 64:
        raise EvidenceError("mosaic must contain 1..64 units")
    seen = set()
    for item in units:
        if not isinstance(item, dict) or not set(item).issubset({"id", "kind", "depends_on", "required", "segments", "separator", "path", "chunk_bytes"}):
            raise EvidenceError("unknown mosaic unit field")
        uid = item.get("id")
        deps = item.get("depends_on", [])
        if not isinstance(uid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", uid) or uid in seen:
            raise EvidenceError("unit ID invalid or repeated")
        if item.get("kind") not in ALLOWED_KINDS or type(item.get("required", True)) is not bool:
            raise EvidenceError("unit kind/required invalid")
        if not isinstance(deps, list) or len(deps) != len(set(map(str, deps))) or any(not isinstance(x, str) or x not in seen for x in deps):
            raise EvidenceError("dependencies must name earlier distinct units")
        seen.add(uid)
    return units

def run_mosaic(ledger: Path, plan_path: Path) -> dict:
    plan = strict_json(plan_path.read_text(encoding="utf-8"))
    units = check_plan(plan)
    prior = {}
    verdicts = []
    for unit in units:
        required = unit.get("required", True)
        missing = [x for x in unit.get("depends_on", []) if prior[x] != "PASS"]
        if missing:
            result = {"verdict": "BLOCKED", "reason": "upstream unit not PASS", "dependency_ids": missing}
        else:
            try:
                result = run_unit(unit)
            except (OSError, ValueError) as exc:
                result = {"verdict": "BLOCKED", "reason": "invalid or inaccessible unit inputs", "error_type": type(exc).__name__}
        prior[unit["id"]] = result["verdict"]
        event = append_event(ledger, "mosaic.unit", {"id": unit["id"], "kind": unit["kind"], "required": required, "result": result})
        verdicts.append({"id": unit["id"], "required": required, "verdict": result["verdict"], "event_sha256": event["head_sha256"]})
    essential = [x["verdict"] for x in verdicts if x["required"]]
    if any(x == "FAIL" for x in essential):
        verdict = "FAIL"
    elif any(x == "BLOCKED" for x in essential):
        verdict = "BLOCKED"
    elif essential and all(x == "PASS" for x in essential):
        verdict = "PASS"
    else:
        verdict = "NOT_RUN"
    final = append_event(ledger, "mosaic.assembly", {"verdict": verdict, "units": verdicts, "required_count": len(essential)})
    return {"verdict": verdict, "units": verdicts, "checkpoint": final}

def main(argv=None):
    p = argparse.ArgumentParser(description="Tesarac local evidence checkpoints; NOT a certified notary")
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("init", "verify", "note", "capture", "partition", "mosaic"):
        c = sub.add_parser(action)
        c.add_argument("--ledger", type=Path, required=True)
        if action == "verify":
            c.add_argument("--expected-sha256")
            c.add_argument("--expected-count", type=int)
        elif action == "note":
            c.add_argument("--text", required=True)
            c.add_argument("--artifact", default="")
        elif action == "capture":
            c.add_argument("--kind", choices=["logcat", "interfaces"], required=True)
        elif action == "partition":
            c.add_argument("--file", type=Path, required=True)
            c.add_argument("--chunk-bytes", type=int, default=65536)
        elif action == "mosaic":
            c.add_argument("--plan", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.action == "init":
            result = init(args.ledger)
        elif args.action == "verify":
            result = verify_bytes(read_ledger(args.ledger), args.expected_sha256, args.expected_count)
        elif args.action == "note":
            result = note(args.ledger, args.text, args.artifact)
        elif args.action == "capture":
            measurement = probe(args.kind)
            result = {"measurement": measurement, "checkpoint": append_event(args.ledger, "capture." + args.kind, measurement)}
        elif args.action == "partition":
            measurement = partition(args.file, args.chunk_bytes)
            result = {"measurement": measurement, "checkpoint": append_event(args.ledger, "partition", measurement)}
        else:
            result = run_mosaic(args.ledger, args.plan)
    except (EvidenceError, OSError, ValueError) as exc:
        print(json.dumps({"verdict": "BLOCKED", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    if isinstance(result, dict) and (result.get("verdict") in {"BLOCKED", "FAIL"} or result.get("measurement", {}).get("verdict") == "BLOCKED"):
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
