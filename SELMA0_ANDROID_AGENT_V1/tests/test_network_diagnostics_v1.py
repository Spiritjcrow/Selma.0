#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selma0_network_diagnostics_android_v1 import (
    audit_router_snapshot_v1,
    plan_transport_v1,
    register_network_diagnostic_tools_v1,
)
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1
from selma0_permission_engine_android_v1 import Selma0PermissionEngineAndroidV1


class OfflineRouterAuditTests(unittest.TestCase):
    def test_router_snapshot_preserves_evidence_without_live_claims(self):
        result = audit_router_snapshot_v1([
            {"name": "T513Z", "mac": "52:49:50:77:4f:9f",
             "ipv4": "192.168.1.192", "status": "off", "band": "5 GHz"},
            {"name": None, "mac": "0a:04:8c:49:a8:81",
             "ipv4": "192.168.1.154", "status": "on",
             "ipv6": ["fe80::804:8cff:fe49:a881"]},
        ])
        self.assertEqual(result["reported_on"], 1)
        self.assertEqual(result["reported_off"], 1)
        self.assertFalse(result["router_access_performed"])
        self.assertFalse(result["live_scan_performed"])
        self.assertFalse(result["unauthorized_access_verified"])
        self.assertTrue(result["devices"][0]["mac_locally_administered"])
        self.assertTrue(result["devices"][1]["mac_locally_administered"])

    def test_empty_snapshot_is_empty_not_successful_discovery(self):
        result = audit_router_snapshot_v1([])
        self.assertEqual(result["device_count"], 0)
        self.assertEqual(result["devices"], [])

    def test_malformed_mac_and_ip_rejected(self):
        for entry in [
            {"mac": "not-a-mac"},
            {"ipv4": "192.168.1.999"},
            {"ipv6": ["bad"]},
            {"status": "admin"},
        ]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                audit_router_snapshot_v1([entry])


class AdaptiveTransportTests(unittest.TestCase):
    def test_quality_ranks_better_live_wifi(self):
        plan = plan_transport_v1([
            {"transport": "cellular", "available": True,
             "latency_ms": 250, "loss_percent": 5, "metered": True},
            {"transport": "wifi", "available": True,
             "latency_ms": 20, "loss_percent": 0,
             "throughput_mbps": 30, "metered": False},
            {"transport": "offline", "available": True},
        ])
        self.assertEqual(plan["selected"], "wifi")
        self.assertFalse(plan["probe_performed"])
        self.assertFalse(plan["switch_performed"])

    def test_changing_carrier_does_not_require_fixed_network_id(self):
        plan = plan_transport_v1([
            {"transport": "wifi", "available": False},
            {"transport": "cellular", "available": True, "metered": True},
        ])
        self.assertEqual(plan["selected"], "cellular")
        self.assertIsNone(plan["ranking"][0]["latency_ms"])

    def test_offline_mode_is_explicit_not_fabricated(self):
        plan = plan_transport_v1([
            {"transport": "wifi", "available": False},
            {"transport": "offline", "available": True},
        ])
        self.assertEqual(plan["selected"], "offline")
        plan = plan_transport_v1([])
        self.assertIsNone(plan["selected"])

    def test_unreported_availability_fails_closed(self):
        with self.assertRaises(ValueError):
            plan_transport_v1([{"transport": "wifi"}])
        with self.assertRaises(ValueError):
            plan_transport_v1([{"transport": "wifi", "available": True,
                                "latency_ms": -3}])


class ToolBoundaryTests(unittest.TestCase):
    def test_snapshot_requires_explicit_sensitive_read_approval(self):
        registry = Selma0ToolRegistryAndroidV1()
        register_network_diagnostic_tools_v1(registry)
        permission = Selma0PermissionEngineAndroidV1()
        snapshot = registry.describe("network.audit_router_snapshot")
        self.assertEqual(snapshot["risk"], "sensitive_read")
        self.assertFalse(permission.evaluate(snapshot).allowed)
        self.assertTrue(permission.evaluate(snapshot, approved=True).allowed)
        planning = registry.describe("network.plan_transport")
        self.assertEqual(planning["risk"], "read")
        self.assertTrue(permission.evaluate(planning).allowed)


if __name__ == "__main__":
    unittest.main()
