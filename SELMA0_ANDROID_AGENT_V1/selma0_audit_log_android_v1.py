import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

SELMA0_BASE_V1 = os.path.expanduser(os.getenv("SELMA0_BASE_V1", "~/SELMA0_ANDROID_AGENT_V1"))
SELMA0_AUDIT_DIR_V1 = os.path.join(SELMA0_BASE_V1, "selma0_audit_android_v1")
SELMA0_COMMAND_AUDIT_V1 = os.path.join(SELMA0_AUDIT_DIR_V1, "command_events_v1.jsonl")

_SECRET_KEYS_V1 = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}


def _utc_now_v1():
    return datetime.now(timezone.utc).isoformat()


def _compact_json_v1(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _redact_v1(value):
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS_V1:
                clean[str(key)] = "[REDACTED]"
            else:
                clean[str(key)] = _redact_v1(item)
        return clean
    if isinstance(value, list):
        return [_redact_v1(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_v1(item) for item in value]
    return value


class Selma0AuditLogAndroidV1:
    """Append-only, hash-chained local audit log for Selma tool activity."""

    def __init__(self, path=SELMA0_COMMAND_AUDIT_V1):
        self.path = os.path.expanduser(path)
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _last_hash_v1(self):
        if not os.path.exists(self.path):
            return "0" * 64
        try:
            with open(self.path, "rb") as handle:
                lines = handle.readlines()
            if not lines:
                return "0" * 64
            row = json.loads(lines[-1].decode("utf-8"))
            return str(row.get("event_hash", "0" * 64))
        except (OSError, ValueError, UnicodeDecodeError):
            return "0" * 64

    def append(self, event_type, details=None, request_id=None):
        with self._lock:
            event = {
                "event_id": str(uuid.uuid4()),
                "request_id": str(request_id or uuid.uuid4()),
                "recorded_at": _utc_now_v1(),
                "unix_time": time.time(),
                "event_type": str(event_type),
                "details": _redact_v1(details if isinstance(details, dict) else {}),
                "previous_hash": self._last_hash_v1(),
            }
            material = _compact_json_v1(event).encode("utf-8")
            event["event_hash"] = hashlib.sha256(material).hexdigest()
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(_compact_json_v1(event) + "\n")
            return event

    def _all_events_v1(self):
        if not os.path.exists(self.path):
            return []
        rows = []
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rows.append(json.loads(line))
                        except ValueError as exc:
                            return None, {
                                "ok": False,
                                "checked": len(rows),
                                "error": "invalid JSON event",
                                "line": line_number,
                                "detail": str(exc),
                            }
            except OSError as exc:
                return None, {
                    "ok": False,
                    "checked": len(rows),
                    "error": "audit log read failed",
                    "detail": str(exc),
                }
        return rows, None

    def recent(self, limit=100):
        limit = max(1, min(int(limit), 500))
        result = self._all_events_v1()
        if isinstance(result, tuple):
            rows, error = result
            if error:
                return []
        else:
            rows = result
        return rows[-limit:]

    def verify_chain(self):
        result = self._all_events_v1()
        if isinstance(result, tuple):
            events, error = result
            if error:
                return error
        else:
            events = result

        previous_hash = "0" * 64
        checked = 0
        for event in events:
            stored_hash = str(event.get("event_hash", ""))
            material = dict(event)
            material.pop("event_hash", None)
            if str(material.get("previous_hash")) != previous_hash:
                return {
                    "ok": False,
                    "checked": checked,
                    "error": "previous hash mismatch",
                }
            computed = hashlib.sha256(_compact_json_v1(material).encode("utf-8")).hexdigest()
            if computed != stored_hash:
                return {
                    "ok": False,
                    "checked": checked,
                    "error": "event hash mismatch",
                }
            previous_hash = stored_hash
            checked += 1
        return {"ok": True, "checked": checked, "tail_hash": previous_hash}
