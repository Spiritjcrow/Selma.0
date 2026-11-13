from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def stable_id(namespace: str, value: Any) -> str:
    """FDTID-1 stable identifier."""
    digest = sha256_hex(canonical_json({"ns": namespace, "value": value}))
    return f"fdtid1:{namespace}:{digest[:32]}"


def ir_build_id(ir: Any) -> str:
    """FDT-IR-1 deterministic build identity."""
    return f"fdtir1:{sha256_hex(canonical_json(ir))}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fmt_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)
