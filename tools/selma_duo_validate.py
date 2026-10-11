#!/usr/bin/env python3
"""Validate a SelmaOS two-role handoff JSON file without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.duo_handoff import validate_exchange  # noqa: E402


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
            payload = json.load(sys.stdin)
        else:
            with open(args.path, "r", encoding="utf-8") as file:
                payload = json.load(file)
        result = validate_exchange(payload)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
