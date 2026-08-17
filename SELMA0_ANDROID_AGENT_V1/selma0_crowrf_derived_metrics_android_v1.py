#!/usr/bin/env python3
import math
from collections import defaultdict

from selma0_crowrf_measurement_store_android_v1 import Selma0CrowRFMeasurementStoreAndroidV1


def _finite_number_v1(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def derive_rssi_summary_v1(store, session_id, limit=100):
    if not isinstance(store, Selma0CrowRFMeasurementStoreAndroidV1):
        raise TypeError("store must be a Selma0CrowRFMeasurementStoreAndroidV1")

    verified = store.verify_session(session_id)
    if not verified.get("ok"):
        raise RuntimeError(f"CrowRF measured session failed integrity verification: {verified.get('reason', 'unknown')}")

    recent = store.recent_scans(session_id=session_id, limit=limit)
    groups = defaultdict(list)
    metadata = {}
    source_event_hashes = []

    for event in reversed(recent.get("events", [])):
        source_event_hashes.append(event.get("event_hash"))
        payload = event.get("payload") or {}
        if payload.get("measurement_kind") != "measured" or payload.get("inference") is not None:
            raise RuntimeError("derived metrics source contains non-measured content")
        for record in payload.get("records", []):
            if not isinstance(record, dict):
                continue
            bssid = str(record.get("bssid") or "").strip().lower()
            rssi = _finite_number_v1(record.get("rssi_dbm"))
            if not bssid or rssi is None:
                continue
            groups[bssid].append(rssi)
            metadata[bssid] = {
                "ssid": record.get("ssid"),
                "frequency_mhz": record.get("frequency_mhz"),
            }

    summaries = []
    for bssid, values in sorted(groups.items()):
        count = len(values)
        mean = sum(values) / count
        variance = sum((value - mean) ** 2 for value in values) / count
        summaries.append(
            {
                "bssid": bssid,
                "ssid": metadata[bssid].get("ssid"),
                "frequency_mhz": metadata[bssid].get("frequency_mhz"),
                "sample_count": count,
                "mean_rssi_dbm": round(mean, 6),
                "min_rssi_dbm": min(values),
                "max_rssi_dbm": max(values),
                "stddev_rssi_db": round(math.sqrt(variance), 6),
            }
        )

    return {
        "ok": True,
        "data_kind": "derived",
        "derivation": "rssi_summary_v1",
        "session_id": str(session_id),
        "source_integrity_verified": True,
        "source_tail_hash": verified.get("tail_hash"),
        "source_event_hashes": [value for value in source_event_hashes if value],
        "network_count": len(summaries),
        "summaries": summaries,
        "claims": {
            "distance": False,
            "geometry": False,
            "csi": False,
            "occupancy": False,
        },
    }


def register_crowrf_derived_tools(registry, store=None):
    store = store or Selma0CrowRFMeasurementStoreAndroidV1()
    registry.register(
        "crowrf.derive_rssi_summary",
        lambda session_id="", limit=100: derive_rssi_summary_v1(
            store=store,
            session_id=session_id,
            limit=limit,
        ),
        risk="sensitive_read",
        description=(
            "Derive rolling RSSI summary statistics from a verified measured CrowRF session. "
            "Output is explicitly derived and does not claim distance, geometry, CSI, or occupancy."
        ),
    )
    return store
