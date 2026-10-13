"""Offline review of imported environmental observations.

Imports are NEVER independently verified facts or public safety warnings.
This module performs no network, device, location or notification operations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from ipaddress import ip_address
from json import dumps
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
MAX_OBSERVATIONS = 1000
MAX_JSON_BYTES = 2_000_000
FIELDS = frozenset({
    "source_record_id", "source_url", "category", "place", "observed_at",
    "reported_severity", "summary",
})
SEVERITIES = frozenset({"info", "watch", "warning", "critical"})
FRESHNESS_HOURS = {
    "air_quality": 72, "heat": 72, "flood": 72, "wildfire": 72,
    "storm": 72, "earthquake": 72, "water": 72,
    "housing": 8760, "waste": 8760, "sanitation": 8760,
}


def _string(value: Any, name: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"invalid {name}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"control character in {name}")
    return value.strip()


def _timestamp(value: Any) -> datetime:
    raw = _string(value, "observed_at", 50)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at requires a timezone")
    return parsed.astimezone(timezone.utc)


def _source_url(value: Any) -> str:
    url = _string(value, "source_url", 1000)
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or
            parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("source_url must be public HTTPS without credentials/query")
    host = parsed.hostname.lower()
    if "." not in host or host.endswith(".local"):
        raise ValueError("source_url host is not public")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("source_url IP literals are not supported")
    return url


def review_snapshot(snapshot: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Return a local, unverified review queue; fail closed on malformed data.

    An HTTPS URL is a citation pointer, NOT verification of its claims or origin.
    """
    if not isinstance(snapshot, dict) or set(snapshot) != {"schema_version", "observations"}:
        raise ValueError("snapshot must contain schema_version and observations only")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    items = snapshot["observations"]
    if not isinstance(items, list) or len(items) > MAX_OBSERVATIONS:
        raise ValueError("observations must be a bounded array")
    now = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    unique: dict[tuple[str, str], tuple[str, dict[str, str]]] = {}
    for idx, entry in enumerate(items):
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise ValueError(f"invalid observation fields at index {idx}")
        normalized = {
            "source_record_id": _string(entry["source_record_id"], "source_record_id", 200),
            "source_url": _source_url(entry["source_url"]),
            "category": _string(entry["category"], "category", 50),
            "place": _string(entry["place"], "place", 200),
            "observed_at": _timestamp(entry["observed_at"]).isoformat(),
            "reported_severity": _string(entry["reported_severity"], "reported_severity", 25),
            "summary": _string(entry["summary"], "summary", 1500),
        }
        if normalized["category"] not in FRESHNESS_HOURS:
            raise ValueError("unsupported category")
        if normalized["reported_severity"] not in SEVERITIES:
            raise ValueError("unsupported reported_severity")
        key = (normalized["source_url"], normalized["source_record_id"])
        digest = sha256(dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if key in unique:
            if unique[key][0] != digest:
                raise ValueError("conflicting records with the same source identity")
            continue
        unique[key] = (digest, normalized)
    output = []
    for digest, record in unique.values():
        observed = _timestamp(record["observed_at"])
        age = now - observed
        if age < -timedelta(minutes=5):
            review_state = "future_timestamp_unverified"
        elif age > timedelta(hours=FRESHNESS_HOURS[record["category"]]):
            review_state = "stale_unverified"
        else:
            review_state = "current_unverified"
        output.append({**record, "content_sha256": digest,
                       "review_state": review_state, "source_verified": False})
    output.sort(key=lambda record: (record["place"], record["category"], record["source_record_id"]))
    return {
        "schema_version": SCHEMA_VERSION, "reviewed_at": now.isoformat(),
        "observations": output, "total": len(output),
        "requires_independent_verification": True,
        "sent_notifications": False, "collected_live_data": False,
    }
