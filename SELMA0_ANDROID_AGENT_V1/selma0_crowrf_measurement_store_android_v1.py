#!/usr/bin/env python3
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from selma0_crowrf_wifi_scan_android_v1 import collect_crowrf_wifi_scan_v1
from selma0_device_bridge_android_v1 import Selma0TermuxDeviceBridgeAndroidV1


GENESIS_HASH_V1 = "0" * 64


def _utc_now_v1():
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_v1(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("CrowRF measurement payload must be JSON serializable") from exc


def _sha256_text_v1(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _default_db_path_v1():
    base = os.getenv("SELMA0_BASE_V1", "").strip()
    if not base:
        base = os.path.join(os.path.expanduser("~"), "SELMA0_ANDROID_AGENT_V1")
    return os.path.join(
        base,
        "selma0_data_android_v1",
        "selma0_crowrf_measurements_android_v1.sqlite3",
    )


def _validate_measured_scan_v1(scan):
    if not isinstance(scan, dict):
        raise ValueError("CrowRF scan must be an object")
    if scan.get("measurement_kind") != "measured":
        raise ValueError("CrowRF measured store accepts measurement_kind='measured' only")
    if scan.get("inference") is not None:
        raise ValueError("inference must remain outside the measured CrowRF store")
    records = scan.get("records")
    if not isinstance(records, list):
        raise ValueError("CrowRF measured scan records must be an array")
    if int(scan.get("record_count", len(records))) != len(records):
        raise ValueError("CrowRF record_count does not match records")
    limitations = scan.get("limitations") or {}
    if not isinstance(limitations, dict):
        raise ValueError("CrowRF limitations must be an object")
    if limitations.get("distance_estimated") is True:
        raise ValueError("estimated distance cannot be stored as a measured CrowRF scan")
    return scan


class Selma0CrowRFMeasurementStoreAndroidV1:
    """Append-only SQLite store for raw/measured CrowRF acquisition sessions.

    This database is intentionally limited to measured acquisition payloads. Future
    derived metrics or inference belong in a separate store/table and must retain a
    link to the source event hash instead of being written into these rows.
    """

    def __init__(self, db_path=None):
        self.db_path = os.path.abspath(os.path.expanduser(db_path or _default_db_path_v1()))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.RLock()
        self._init_db_v1()

    def _connect_v1(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _init_db_v1(self):
        with self._connect_v1() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS crowrf_sessions_v1 (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    label TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS crowrf_scan_events_v1 (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    collected_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    FOREIGN KEY(session_id) REFERENCES crowrf_sessions_v1(session_id),
                    UNIQUE(session_id, sequence)
                );

                CREATE TRIGGER IF NOT EXISTS crowrf_sessions_no_update_v1
                BEFORE UPDATE ON crowrf_sessions_v1
                BEGIN SELECT RAISE(ABORT, 'CrowRF sessions are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS crowrf_sessions_no_delete_v1
                BEFORE DELETE ON crowrf_sessions_v1
                BEGIN SELECT RAISE(ABORT, 'CrowRF sessions are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS crowrf_events_no_update_v1
                BEFORE UPDATE ON crowrf_scan_events_v1
                BEGIN SELECT RAISE(ABORT, 'CrowRF measurements are append-only'); END;

                CREATE TRIGGER IF NOT EXISTS crowrf_events_no_delete_v1
                BEFORE DELETE ON crowrf_scan_events_v1
                BEGIN SELECT RAISE(ABORT, 'CrowRF measurements are append-only'); END;
                """
            )

    def start_session(self, label="", metadata=None, session_id=None):
        label = str(label or "")[:200]
        metadata = metadata or {}
        if not isinstance(metadata, dict):
            raise ValueError("session metadata must be an object")
        session_id = str(session_id or uuid.uuid4())
        if len(session_id) > 128:
            raise ValueError("session_id is too long")
        created_at = _utc_now_v1()
        metadata_json = _canonical_json_v1(metadata)
        with self._lock, self._connect_v1() as connection:
            connection.execute(
                "INSERT INTO crowrf_sessions_v1(session_id, created_at, label, metadata_json) VALUES(?,?,?,?)",
                (session_id, created_at, label, metadata_json),
            )
        return {
            "ok": True,
            "session_id": session_id,
            "created_at": created_at,
            "label": label,
            "measurement_kind": "measured",
        }

    def record_scan(self, session_id, scan):
        session_id = str(session_id or "").strip()
        if not session_id:
            raise ValueError("session_id is required")
        scan = _validate_measured_scan_v1(scan)
        payload_json = _canonical_json_v1(scan)
        payload_sha256 = _sha256_text_v1(payload_json)
        collected_at = str(scan.get("collected_at") or _utc_now_v1())
        source = str(scan.get("source") or "unknown")[:300]
        record_count = len(scan["records"])

        with self._lock, self._connect_v1() as connection:
            session = connection.execute(
                "SELECT session_id FROM crowrf_sessions_v1 WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise ValueError("unknown CrowRF session_id")
            previous = connection.execute(
                "SELECT sequence, event_hash FROM crowrf_scan_events_v1 WHERE session_id=? ORDER BY sequence DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            sequence = 1 if previous is None else int(previous["sequence"]) + 1
            prev_hash = GENESIS_HASH_V1 if previous is None else str(previous["event_hash"])
            event_material = {
                "session_id": session_id,
                "sequence": sequence,
                "collected_at": collected_at,
                "source": source,
                "record_count": record_count,
                "payload_sha256": payload_sha256,
                "prev_hash": prev_hash,
            }
            event_hash = _sha256_text_v1(_canonical_json_v1(event_material))
            cursor = connection.execute(
                """
                INSERT INTO crowrf_scan_events_v1(
                    session_id, sequence, collected_at, source, record_count,
                    payload_json, payload_sha256, prev_hash, event_hash
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    session_id,
                    sequence,
                    collected_at,
                    source,
                    record_count,
                    payload_json,
                    payload_sha256,
                    prev_hash,
                    event_hash,
                ),
            )
            event_id = int(cursor.lastrowid)
        return {
            "ok": True,
            "event_id": event_id,
            "session_id": session_id,
            "sequence": sequence,
            "record_count": record_count,
            "payload_sha256": payload_sha256,
            "event_hash": event_hash,
            "measurement_kind": "measured",
        }

    def capture_wifi_scan(self, session_id, bridge=None):
        bridge = bridge or Selma0TermuxDeviceBridgeAndroidV1()
        scan = collect_crowrf_wifi_scan_v1(bridge=bridge)
        stored = self.record_scan(session_id=session_id, scan=scan)
        stored["scan"] = scan
        return stored

    def session_status(self, session_id):
        session_id = str(session_id or "").strip()
        with self._connect_v1() as connection:
            session = connection.execute(
                "SELECT session_id, created_at, label FROM crowrf_sessions_v1 WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise ValueError("unknown CrowRF session_id")
            aggregate = connection.execute(
                "SELECT COUNT(*) AS event_count, COALESCE(SUM(record_count),0) AS observation_count, MAX(sequence) AS last_sequence FROM crowrf_scan_events_v1 WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return {
            "ok": True,
            "session_id": session_id,
            "created_at": session["created_at"],
            "label": session["label"],
            "event_count": int(aggregate["event_count"] or 0),
            "observation_count": int(aggregate["observation_count"] or 0),
            "last_sequence": int(aggregate["last_sequence"] or 0),
            "measurement_kind": "measured",
        }

    def recent_scans(self, session_id, limit=20):
        session_id = str(session_id or "").strip()
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be an integer") from exc
        limit = max(1, min(limit, 200))
        with self._connect_v1() as connection:
            rows = connection.execute(
                """
                SELECT event_id, sequence, collected_at, source, record_count,
                       payload_json, payload_sha256, prev_hash, event_hash
                FROM crowrf_scan_events_v1
                WHERE session_id=? ORDER BY sequence DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return {
            "ok": True,
            "session_id": session_id,
            "measurement_kind": "measured",
            "events": [
                {
                    "event_id": int(row["event_id"]),
                    "sequence": int(row["sequence"]),
                    "collected_at": row["collected_at"],
                    "source": row["source"],
                    "record_count": int(row["record_count"]),
                    "payload": json.loads(row["payload_json"]),
                    "payload_sha256": row["payload_sha256"],
                    "prev_hash": row["prev_hash"],
                    "event_hash": row["event_hash"],
                }
                for row in rows
            ],
        }

    def verify_session(self, session_id):
        session_id = str(session_id or "").strip()
        with self._connect_v1() as connection:
            rows = connection.execute(
                """
                SELECT sequence, collected_at, source, record_count, payload_json,
                       payload_sha256, prev_hash, event_hash
                FROM crowrf_scan_events_v1 WHERE session_id=? ORDER BY sequence ASC
                """,
                (session_id,),
            ).fetchall()
        expected_prev = GENESIS_HASH_V1
        for row in rows:
            payload_sha256 = _sha256_text_v1(row["payload_json"])
            if payload_sha256 != row["payload_sha256"]:
                return {"ok": False, "reason": "payload hash mismatch", "sequence": int(row["sequence"])}
            if row["prev_hash"] != expected_prev:
                return {"ok": False, "reason": "previous hash mismatch", "sequence": int(row["sequence"])}
            material = {
                "session_id": session_id,
                "sequence": int(row["sequence"]),
                "collected_at": row["collected_at"],
                "source": row["source"],
                "record_count": int(row["record_count"]),
                "payload_sha256": row["payload_sha256"],
                "prev_hash": row["prev_hash"],
            }
            event_hash = _sha256_text_v1(_canonical_json_v1(material))
            if event_hash != row["event_hash"]:
                return {"ok": False, "reason": "event hash mismatch", "sequence": int(row["sequence"])}
            expected_prev = row["event_hash"]
        return {"ok": True, "session_id": session_id, "event_count": len(rows), "tail_hash": expected_prev}


def register_crowrf_measurement_store_tools(registry, store=None, bridge=None):
    store = store or Selma0CrowRFMeasurementStoreAndroidV1()
    bridge = bridge or Selma0TermuxDeviceBridgeAndroidV1()
    registry.register(
        "crowrf.session_start",
        lambda label="", metadata=None: store.start_session(label=label, metadata=metadata),
        risk="write",
        description="Create an append-only local CrowRF measured-acquisition session.",
    )
    registry.register(
        "crowrf.capture_wifi_scan",
        lambda session_id="": store.capture_wifi_scan(session_id=session_id, bridge=bridge),
        risk="write",
        description="Capture an approved sensitive Wi-Fi scan and append it to the measured CrowRF session store.",
    )
    registry.register(
        "crowrf.session_status",
        lambda session_id="": store.session_status(session_id=session_id),
        risk="read",
        description="Return CrowRF session counts without exposing nearby network identities.",
    )
    registry.register(
        "crowrf.session_recent",
        lambda session_id="", limit=20: store.recent_scans(session_id=session_id, limit=limit),
        risk="sensitive_read",
        description="Read recent measured CrowRF scans; may expose SSID/BSSID location context.",
    )
    registry.register(
        "crowrf.session_verify",
        lambda session_id="": store.verify_session(session_id=session_id),
        risk="read",
        description="Verify the append-only CrowRF measurement hash chain without exposing scan payloads.",
    )
    return store
