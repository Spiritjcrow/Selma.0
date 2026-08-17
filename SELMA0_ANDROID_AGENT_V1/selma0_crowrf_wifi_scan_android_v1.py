#!/usr/bin/env python3
from copy import deepcopy

from selma0_device_bridge_android_v1 import Selma0TermuxDeviceBridgeAndroidV1


def _first_v1(record, *keys):
    for key in keys:
        if key in record and record.get(key) is not None:
            return record.get(key)
    return None


def _number_v1(value, cast):
    if value is None or value == "":
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def normalize_wifi_scan_record_v1(record):
    if not isinstance(record, dict):
        raise ValueError("Wi-Fi scan record must be an object")

    frequency = _number_v1(_first_v1(record, "frequency_mhz", "frequency", "freq"), int)
    rssi = _number_v1(_first_v1(record, "rssi_dbm", "rssi", "level"), int)

    return {
        "ssid": _first_v1(record, "ssid", "SSID"),
        "bssid": _first_v1(record, "bssid", "BSSID"),
        "frequency_mhz": frequency,
        "rssi_dbm": rssi,
        "capabilities": _first_v1(record, "capabilities", "Capabilities"),
        "timestamp": _first_v1(record, "timestamp", "timestamp_us", "seen"),
        "raw": deepcopy(record),
    }


def collect_crowrf_wifi_scan_v1(bridge=None):
    bridge = bridge or Selma0TermuxDeviceBridgeAndroidV1()
    result = bridge.read_json("wifi_scan")
    payload = result.get("data")

    if payload is None:
        records = []
    elif isinstance(payload, list):
        records = payload
    else:
        raise RuntimeError("Termux:API Wi-Fi scan output must be a JSON array")

    normalized = [normalize_wifi_scan_record_v1(record) for record in records]
    return {
        "ok": True,
        "measurement_kind": "measured",
        "source": "termux-api:wifi-scaninfo",
        "device_local": True,
        "collected_at": result.get("collected_at"),
        "record_count": len(normalized),
        "records": normalized,
        "inference": None,
        "limitations": {
            "csi_available": False,
            "geometry_measured": False,
            "distance_estimated": False,
            "note": "Rootless Wi-Fi scan telemetry is RSSI/BSSID/frequency metadata, not CSI or measured geometry.",
        },
    }


def register_crowrf_tools(registry, bridge=None):
    bridge = bridge or Selma0TermuxDeviceBridgeAndroidV1()
    registry.register(
        "crowrf.wifi_scan",
        lambda: collect_crowrf_wifi_scan_v1(bridge=bridge),
        risk="sensitive_read",
        description=(
            "Collect measured rootless Wi-Fi scan telemetry for CrowRF through Termux:API. "
            "Explicit approval is required because nearby SSID/BSSID data can expose location context. "
            "Returns RSSI/BSSID/frequency metadata only; does not fabricate CSI or geometry."
        ),
    )
    return bridge
