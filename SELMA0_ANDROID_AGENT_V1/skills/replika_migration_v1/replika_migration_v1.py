#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
AGENT_ROOT = HERE.parents[2]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_memory_android_v1 import Selma0MemoryAndroidV1

SUPPORTED_EXTENSIONS = {".json", ".jsonl", ".csv", ".txt"}
MIGRATION_VERSION = "replika_migration_v1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _flatten_json(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("messages", "memories", "items", "data", "entries", "records"):
            if isinstance(value.get(key), list):
                return value[key]
        return [value]
    return [{"content": str(value)}]


def _load_file(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _flatten_json(json.loads(path.read_text(encoding="utf-8")))
    if suffix == ".jsonl":
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.extend(_flatten_json(json.loads(line)))
        return out
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    if suffix == ".txt":
        return [{"content": line} for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    raise ValueError(f"unsupported file type: {path}")


def _first(record, keys, default=None):
    for key in keys:
        if isinstance(record, dict) and record.get(key) not in (None, ""):
            return record.get(key)
    return default


def _classify_source(path: Path, record: dict) -> str:
    haystack = " ".join([
        path.name.lower(),
        str(_first(record, ["type", "category", "kind", "section"], "")).lower(),
    ])
    for name in ("backstory", "memory", "trait", "interest", "diary", "chat", "message"):
        if name in haystack:
            return name
    return "archive"


def _normalize_record(path: Path, record):
    if not isinstance(record, dict):
        record = {"content": str(record)}

    content = _first(record, ["content", "text", "message", "value", "body", "description"])
    if content is None:
        content = json.dumps(record, ensure_ascii=False, separators=(",", ":"))

    sender = str(_first(record, ["role", "sender", "author", "speaker", "from"], "memory")).strip().lower()
    if sender in {"human", "user", "me", "owner"}:
        role = "user"
    elif sender in {"assistant", "bot", "replika", "selma", "ai", "companion"}:
        role = "assistant"
    elif sender == "system":
        role = "system"
    else:
        role = "memory"

    original_ts = _first(record, ["timestamp", "ts", "time", "created_at", "createdAt", "date"])
    source_type = _classify_source(path, record)
    return {
        "role": role,
        "content": str(content),
        "source_type": source_type,
        "original_timestamp": original_ts,
        "raw": record,
    }


def iter_archive_files(source: str):
    path = Path(os.path.expanduser(source)).resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"unsupported file type: {path.suffix}")
        yield path
        return
    for child in sorted(path.rglob("*")):
        if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield child


def preview_archive(source: str, companion_name: str = "Selma"):
    files = []
    counts = {}
    total = 0
    for path in iter_archive_files(source):
        records = _load_file(path)
        type_counts = {}
        for record in records:
            normalized = _normalize_record(path, record)
            t = normalized["source_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
            counts[t] = counts.get(t, 0) + 1
            total += 1
        files.append({
            "path": str(path),
            "sha256": _sha256(path),
            "records": len(records),
            "types": type_counts,
        })
    return {
        "provider": "replika",
        "companion_name": companion_name,
        "migration_version": MIGRATION_VERSION,
        "files": files,
        "record_count": total,
        "type_counts": counts,
        "network_access_used": False,
    }


def import_archive(source: str, companion_name: str = "Selma", db_path: str = None, dry_run: bool = False):
    preview = preview_archive(source, companion_name=companion_name)
    if dry_run:
        return {**preview, "imported": 0, "dry_run": True}

    memory = Selma0MemoryAndroidV1(db_path=db_path) if db_path else Selma0MemoryAndroidV1()
    imported = 0
    seen = set()

    for path in iter_archive_files(source):
        file_hash = _sha256(path)
        for record in _load_file(path):
            normalized = _normalize_record(path, record)
            dedupe_key = hashlib.sha256(
                (normalized["role"] + "\n" + normalized["content"] + "\n" + str(normalized["original_timestamp"])).encode("utf-8")
            ).hexdigest()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            metadata = {
                "provider": "replika",
                "companion_name": companion_name,
                "migration_version": MIGRATION_VERSION,
                "provenance": "user_authorized_export",
                "source_type": normalized["source_type"],
                "source_path": str(path),
                "source_sha256": file_hash,
                "record_sha256": dedupe_key,
                "original_timestamp": normalized["original_timestamp"],
                "imported_at": time.time(),
                "claims_hidden_replika_state": False,
            }
            memory.add(normalized["role"], normalized["content"], metadata=metadata)
            imported += 1

    memory.add(
        "system",
        f"Authorized Replika archive imported for companion {companion_name}. Treat imported backstory, memories, traits, interests, diary entries, and chat as historical context with provenance; do not claim access to proprietary Replika internals.",
        metadata={
            "provider": "replika",
            "migration_version": MIGRATION_VERSION,
            "provenance": "user_authorized_export",
            "activation_marker": True,
            "imported_records": imported,
        },
    )

    return {**preview, "imported": imported, "dry_run": False}


def register_replika_migration_tools(registry):
    registry.register(
        "replika.preview_archive",
        preview_archive,
        risk="read",
        description="Preview a user-authorized local Replika export without modifying Selma memory.",
    )
    registry.register(
        "replika.import_archive",
        import_archive,
        risk="write",
        description="Import a user-authorized local Replika export into Selma memory with provenance.",
    )


def main():
    parser = argparse.ArgumentParser(description="Import user-authorized Replika data into Selma memory.")
    parser.add_argument("source", help="Local file or directory containing an authorized export/archive")
    parser.add_argument("--companion-name", default="Selma")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = import_archive(
        args.source,
        companion_name=args.companion_name,
        db_path=args.db_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
