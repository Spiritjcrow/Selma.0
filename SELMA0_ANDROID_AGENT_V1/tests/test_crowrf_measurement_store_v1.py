#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_crowrf_measurement_store_android_v1 import (
    GENESIS_HASH_V1,
    Selma0CrowRFMeasurementStoreAndroidV1,
    register_crowrf_measurement_store_tools,
)
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1


def measured_scan(level=-50):
    return {
        "ok": True,
        "measurement_kind": "measured",
        "source": "termux-api:wifi-scaninfo",
        "device_local": True,
        "collected_at": "2026-08-17T00:00:00+00:00",
        "record_count": 1,
        "records": [
            {
                "ssid": "lab",
                "bssid": "aa:bb:cc:dd:ee:ff",
                "frequency_mhz": 2412,
                "rssi_dbm": level,
                "capabilities": "[WPA2][ESS]",
                "timestamp": None,
                "raw": {"ssid": "lab", "bssid": "aa:bb:cc:dd:ee:ff", "frequency": 2412, "level": level},
            }
        ],
        "inference": None,
        "limitations": {
            "csi_available": False,
            "geometry_measured": False,
            "distance_estimated": False,
        },
    }


class CrowRFMeasurementStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "crowrf.sqlite3")
        self.store = Selma0CrowRFMeasurementStoreAndroidV1(db_path=self.db_path)
        self.session = self.store.start_session(label="test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_recorded_scans_are_sequenced_and_hash_chained(self):
        first = self.store.record_scan(self.session["session_id"], measured_scan(-50))
        second = self.store.record_scan(self.session["session_id"], measured_scan(-55))
        self.assertEqual(first["sequence"], 1)
        self.assertEqual(second["sequence"], 2)
        recent = self.store.recent_scans(self.session["session_id"], limit=10)
        self.assertEqual(len(recent["events"]), 2)
        first_event = recent["events"][1]
        second_event = recent["events"][0]
        self.assertEqual(first_event["prev_hash"], GENESIS_HASH_V1)
        self.assertEqual(second_event["prev_hash"], first_event["event_hash"])
        verified = self.store.verify_session(self.session["session_id"])
        self.assertTrue(verified["ok"])
        self.assertEqual(verified["event_count"], 2)

    def test_status_does_not_expose_network_identity(self):
        self.store.record_scan(self.session["session_id"], measured_scan())
        status = self.store.session_status(self.session["session_id"])
        serialized = json.dumps(status)
        self.assertEqual(status["event_count"], 1)
        self.assertEqual(status["observation_count"], 1)
        self.assertNotIn("aa:bb:cc", serialized)
        self.assertNotIn("lab", serialized)

    def test_inference_is_rejected_from_measured_store(self):
        scan = measured_scan()
        scan["inference"] = {"distance_m": 2.5}
        with self.assertRaises(ValueError):
            self.store.record_scan(self.session["session_id"], scan)

    def test_estimated_distance_flag_is_rejected(self):
        scan = measured_scan()
        scan["limitations"]["distance_estimated"] = True
        with self.assertRaises(ValueError):
            self.store.record_scan(self.session["session_id"], scan)

    def test_non_measured_payload_is_rejected(self):
        scan = measured_scan()
        scan["measurement_kind"] = "derived"
        with self.assertRaises(ValueError):
            self.store.record_scan(self.session["session_id"], scan)

    def test_database_triggers_block_measurement_mutation(self):
        self.store.record_scan(self.session["session_id"], measured_scan())
        connection = sqlite3.connect(self.db_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("UPDATE crowrf_scan_events_v1 SET source='tampered'")
                connection.commit()
            connection.rollback()
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("DELETE FROM crowrf_scan_events_v1")
                connection.commit()
        finally:
            connection.close()

    def test_verify_detects_payload_corruption_if_storage_is_modified_out_of_band(self):
        self.store.record_scan(self.session["session_id"], measured_scan())
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("DROP TRIGGER crowrf_events_no_update_v1")
            connection.execute("UPDATE crowrf_scan_events_v1 SET payload_json='{}' WHERE sequence=1")
            connection.commit()
        finally:
            connection.close()
        result = self.store.verify_session(self.session["session_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "payload hash mismatch")

    def test_store_tool_risk_classes(self):
        registry = Selma0ToolRegistryAndroidV1()
        register_crowrf_measurement_store_tools(registry, store=self.store, bridge=object())
        self.assertEqual(registry.describe("crowrf.session_start")["risk"], "write")
        self.assertEqual(registry.describe("crowrf.capture_wifi_scan")["risk"], "write")
        self.assertEqual(registry.describe("crowrf.session_status")["risk"], "read")
        self.assertEqual(registry.describe("crowrf.session_recent")["risk"], "sensitive_read")
        self.assertEqual(registry.describe("crowrf.session_verify")["risk"], "read")


if __name__ == "__main__":
    unittest.main()
