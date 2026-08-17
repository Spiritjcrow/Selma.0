#!/usr/bin/env python3
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_crowrf_derived_metrics_android_v1 import (
    derive_rssi_summary_v1,
    register_crowrf_derived_tools,
)
from selma0_crowrf_measurement_store_android_v1 import Selma0CrowRFMeasurementStoreAndroidV1
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1


def measured_scan(level, bssid="aa:bb:cc:dd:ee:ff", ssid="lab"):
    return {
        "ok": True,
        "measurement_kind": "measured",
        "source": "termux-api:wifi-scaninfo",
        "device_local": True,
        "collected_at": "2026-08-17T00:00:00+00:00",
        "record_count": 1,
        "records": [
            {
                "ssid": ssid,
                "bssid": bssid,
                "frequency_mhz": 2412,
                "rssi_dbm": level,
                "capabilities": "[WPA2][ESS]",
                "timestamp": None,
                "raw": {"ssid": ssid, "bssid": bssid, "frequency": 2412, "level": level},
            }
        ],
        "inference": None,
        "limitations": {
            "csi_available": False,
            "geometry_measured": False,
            "distance_estimated": False,
        },
    }


class CrowRFDerivedMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "crowrf.sqlite3")
        self.store = Selma0CrowRFMeasurementStoreAndroidV1(db_path=self.db_path)
        self.session = self.store.start_session(label="derived-test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rssi_summary_is_explicitly_derived(self):
        self.store.record_scan(self.session["session_id"], measured_scan(-50))
        self.store.record_scan(self.session["session_id"], measured_scan(-60))
        result = derive_rssi_summary_v1(self.store, self.session["session_id"])
        self.assertEqual(result["data_kind"], "derived")
        self.assertTrue(result["source_integrity_verified"])
        self.assertEqual(result["network_count"], 1)
        summary = result["summaries"][0]
        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["mean_rssi_dbm"], -55.0)
        self.assertEqual(summary["min_rssi_dbm"], -60.0)
        self.assertEqual(summary["max_rssi_dbm"], -50.0)
        self.assertEqual(summary["stddev_rssi_db"], 5.0)

    def test_derived_output_makes_no_physical_claims(self):
        self.store.record_scan(self.session["session_id"], measured_scan(-50))
        result = derive_rssi_summary_v1(self.store, self.session["session_id"])
        self.assertEqual(
            result["claims"],
            {"distance": False, "geometry": False, "csi": False, "occupancy": False},
        )
        self.assertNotIn("distance_m", result["summaries"][0])

    def test_corrupted_measured_source_blocks_derivation(self):
        self.store.record_scan(self.session["session_id"], measured_scan(-50))
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("DROP TRIGGER crowrf_events_no_update_v1")
            connection.execute("UPDATE crowrf_scan_events_v1 SET payload_json='{}' WHERE sequence=1")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RuntimeError):
            derive_rssi_summary_v1(self.store, self.session["session_id"])

    def test_invalid_rssi_records_are_skipped_not_invented(self):
        scan = measured_scan(-50)
        scan["records"][0]["rssi_dbm"] = None
        self.store.record_scan(self.session["session_id"], scan)
        result = derive_rssi_summary_v1(self.store, self.session["session_id"])
        self.assertEqual(result["network_count"], 0)
        self.assertEqual(result["summaries"], [])

    def test_derived_tool_is_sensitive_read(self):
        registry = Selma0ToolRegistryAndroidV1()
        register_crowrf_derived_tools(registry, store=self.store)
        self.assertEqual(registry.describe("crowrf.derive_rssi_summary")["risk"], "sensitive_read")


if __name__ == "__main__":
    unittest.main()
