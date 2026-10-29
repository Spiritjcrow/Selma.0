#!/usr/bin/env python3
"""Validate a SelmaOS two-role handoff JSON file without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.duo_handoff import validate_exchange  # noqa: E402

# Well above the maximum possible two-record v0.1 payload. Read at most one
# additional byte so oversized input never reaches the JSON parser.
MAX_JSON_BYTES = 1_048_576


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Fail closed on ambiguous JSON keys, including nested objects."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _load_bounded_json(stream):
    raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds maximum 1048576 bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds parser limit") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline validation only: does NOT sync two phones"
    )
    parser.add_argument(
        "path", nargs="?", default="-", help="JSON array path, or - for stdin"
    )
    args = parser.parse_args(argv)
    try:
        if args.path == "-":
            payload = _load_bounded_json(sys.stdin.buffer)
        else:
            with open(args.path, "rb") as file:
                payload = _load_bounded_json(file)
        result = validate_exchange(payload)
    except OSError:
        # OSError text includes the supplied path, which can contain private
        # filenames or directories. Do not echo it into captured CLI logs.
        print(json.dumps({"ok": False, "error": "input read failed"}))
        return 2
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
