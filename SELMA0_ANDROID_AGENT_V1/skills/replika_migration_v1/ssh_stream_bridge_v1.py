#!/usr/bin/env python3
"""Receive a user-authorized archive over stdin and hand it to Selma's migration importer.

This process performs no network access itself. The SSH transport is established externally by
an operator to a host/device they control, e.g.:

  ssh user@owned-host 'cat ~/exports/selma.json' | \
    python ssh_stream_bridge_v1.py --format json --preview

Import requires --confirmed-import. Input is staged locally with mode 0600, hashed, and then
processed by replika_migration_v1.py.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from replika_migration_v1 import import_archive, preview_archive

SUPPORTED_FORMATS = {"json", "jsonl", "csv", "txt"}
MAX_BYTES_DEFAULT = 256 * 1024 * 1024


def _read_stdin_limited(max_bytes: int) -> bytes:
    data = bytearray()
    while True:
        chunk = sys.stdin.buffer.read(min(1024 * 1024, max_bytes + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise ValueError(f"stream exceeds configured limit of {max_bytes} bytes")
    if not data:
        raise ValueError("empty input stream")
    return bytes(data)


def _stage(data: bytes, fmt: str, staging_dir: str | None = None) -> tuple[Path, str]:
    suffix = "." + fmt
    root = Path(os.path.expanduser(staging_dir)).resolve() if staging_dir else None
    if root:
        root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="selma_replika_stream_", suffix=suffix, dir=str(root))
    else:
        fd, name = tempfile.mkstemp(prefix="selma_replika_stream_", suffix=suffix)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    path = Path(name)
    digest = hashlib.sha256(data).hexdigest()
    return path, digest


def main():
    parser = argparse.ArgumentParser(
        description="Stage an authorized SSH/stdin archive and preview or import it into Selma memory."
    )
    parser.add_argument("--format", required=True, choices=sorted(SUPPORTED_FORMATS))
    parser.add_argument("--companion-name", default="Selma")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--staging-dir", default=None)
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES_DEFAULT)
    parser.add_argument("--preview", action="store_true", help="Preview only; this is the default behavior.")
    parser.add_argument(
        "--confirmed-import",
        action="store_true",
        help="Explicitly authorize writing the staged archive into Selma memory.",
    )
    parser.add_argument(
        "--keep-staged",
        action="store_true",
        help="Keep the staged file after processing; otherwise it is removed.",
    )
    args = parser.parse_args()

    if args.max_bytes <= 0:
        raise SystemExit("--max-bytes must be positive")
    if args.preview and args.confirmed_import:
        raise SystemExit("choose preview or confirmed import, not both")

    staged = None
    try:
        data = _read_stdin_limited(args.max_bytes)
        staged, digest = _stage(data, args.format, args.staging_dir)
        envelope = {
            "transport": "external_ssh_or_stdin",
            "network_access_by_bridge": False,
            "staged_path": str(staged),
            "staged_sha256": digest,
            "bytes": len(data),
            "companion_name": args.companion_name,
            "provenance": "user_authorized_stream",
            "claims_hidden_replika_state": False,
        }

        if args.confirmed_import:
            result = import_archive(
                str(staged),
                companion_name=args.companion_name,
                db_path=args.db_path,
                dry_run=False,
            )
            envelope["mode"] = "confirmed_import"
            envelope["result"] = result
        else:
            result = preview_archive(str(staged), companion_name=args.companion_name)
            envelope["mode"] = "preview"
            envelope["result"] = result

        print(json.dumps(envelope, indent=2, ensure_ascii=False))
    finally:
        if staged and staged.exists() and not args.keep_staged:
            try:
                staged.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
