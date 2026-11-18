from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from memory_store import MemoryStore


TEXT_KEYS = ("content", "text", "message", "body")
ROLE_KEYS = ("role", "sender", "author", "speaker")
TIME_KEYS = ("created_at", "timestamp", "time", "date")
ID_KEYS = ("id", "message_id", "uuid", "record_id")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _first_scalar(d: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = d.get(key)
        if isinstance(value, (str, int, float)):
            text = str(value).strip()
            if text:
                return text
        if isinstance(value, dict):
            nested = value.get("name") or value.get("role")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _content_from_chatgpt_message(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            text = "\n".join(
                str(part) for part in parts if isinstance(part, (str, int, float))
            ).strip()
            if text:
                return text
    return _first_scalar(message, TEXT_KEYS)


def iter_chatgpt_export(payload: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(payload, list):
        return
    for conversation in payload:
        if not isinstance(conversation, dict):
            continue
        mapping = conversation.get("mapping")
        if not isinstance(mapping, dict):
            continue
        title = conversation.get("title")
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            message = node.get("message")
            if not isinstance(message, dict):
                continue
            text = _content_from_chatgpt_message(message)
            if not text:
                continue
            author = message.get("author")
            role = author.get("role") if isinstance(author, dict) else None
            created = message.get("create_time")
            source_id = message.get("id") or node_id
            yield {
                "content": text,
                "role": str(role) if role else None,
                "created_at": str(created) if created is not None else None,
                "source_record_id": str(source_id) if source_id else None,
                "provenance_extra": {"conversation_title": title},
            }


def iter_generic_records(payload: Any) -> Iterable[dict[str, Any]]:
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(reversed(item))
            continue
        if not isinstance(item, dict):
            continue

        text = _first_scalar(item, TEXT_KEYS)
        if text:
            yield {
                "content": text,
                "role": _first_scalar(item, ROLE_KEYS),
                "created_at": _first_scalar(item, TIME_KEYS),
                "source_record_id": _first_scalar(item, ID_KEYS),
                "provenance_extra": {},
            }

        for value in item.values():
            if isinstance(value, (dict, list)):
                stack.append(value)


def load_records(path: Path, source: str) -> Iterable[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if source == "chatgpt":
            chatgpt_rows = list(iter_chatgpt_export(payload))
            if chatgpt_rows:
                yield from chatgpt_rows
                return
        yield from iter_generic_records(payload)
        return

    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield from iter_generic_records(json.loads(line))
        return

    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                yield from iter_generic_records(row)
        return

    if suffix == ".txt":
        text = path.read_text(encoding="utf-8").strip()
        if text:
            yield {
                "content": text,
                "role": None,
                "created_at": None,
                "source_record_id": None,
                "provenance_extra": {},
            }
        return

    raise ValueError(f"unsupported file type: {suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import a user-authorized export into Selma Memory Bridge."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--source",
        required=True,
        choices=("chatgpt", "replika", "selma", "manual"),
    )
    args = parser.parse_args()

    path = args.path.expanduser().resolve()
    if not path.is_file():
        parser.error(f"not a file: {path}")

    original_digest = file_sha256(path)
    provenance_base = {
        "authorization": "user_supplied_export",
        "original_filename": path.name,
        "original_file_sha256": original_digest,
    }

    rows = []
    for record in load_records(path, args.source):
        provenance = dict(provenance_base)
        provenance.update(record.pop("provenance_extra", {}))
        rows.append({"source": args.source, "provenance": provenance, **record})

    result = MemoryStore().add_many(rows)
    print(
        json.dumps(
            {
                "source": args.source,
                "file": path.name,
                "file_sha256": original_digest,
                **result,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
