"""Local-only EarthWatch JSON snapshot review: python -m tools.earthwatch_review FILE."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.earthwatch import MAX_JSON_BYTES, review_snapshot


def run(path: Path) -> dict:
    with path.open("rb") as f:
        raw = f.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("input exceeds maximum size")
    return review_snapshot(json.loads(raw))


def main() -> None:
    parser = argparse.ArgumentParser(description="Review an offline EarthWatch snapshot (unverified)")
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.snapshot), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
