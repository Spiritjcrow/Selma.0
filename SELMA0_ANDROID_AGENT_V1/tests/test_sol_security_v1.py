#!/usr/bin/env python3
"""Offline tests: no live network targets or attack traffic."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selma0_permission_engine_android_v1 import Selma0PermissionEngineAndroidV1
from selma0_sol_security_android_v1 import (
    _classify_host, blue_exposure_review, red_isolated_selftest,
    register_sol_security_tools,
)
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1


class SolBlueTests(unittest.TestCase):
    def test_loopback_defaults_do_not_claim_exposure(self):
        result = blue_exposure_review(bind_host="127.0.0.1", model_host="::1",
                                      authentication_enabled=False)
        self.assertEqual(result["categories"]["bind_host"], "loopback")
        self.assertFalse(any(f["severity"] == "high" for f in result["findings"]))
        self.assertFalse(result["live_exposure_verified"])
        self.assertFalse(result["network_activity"])

    def test_wildcard_without_auth_is_high_risk(self):
        result = blue_exposure_review(bind_host="0.0.0.0", model_host="localhost",
                                      authentication_enabled=False)
        self.assertGreaterEqual(sum(f["severity"] == "high" for f in result["findings"]), 2)

    def test_unsafe_host_strings_are_not_resolved(self):
        self.assertEqual(_classify_host("https://example.com/key"), "invalid")
        self.assertEqual(_classify_host("model.example.org"), "hostname_unverified")
        self.assertEqual(_classify_host("[::1]"), "loopback")

    def test_published_poellm_ioc_match_only_supplied_logs(self):
        result = blue_exposure_review(
            bind_host="localhost", observed_ips=["92.119.164.50", "1.1.1.1", "bad-ip"]
        )
        self.assertEqual(result["poellm_historical_ioc_matches"], ["92.119.164.50"])
        self.assertEqual(result["invalid_ip_count"], 1)
        self.assertFalse(result["network_activity"])

    def test_caller_input_is_bounded(self):
        with self.assertRaises(ValueError):
            blue_exposure_review(observed_ips=["1.2.3.4"] * 65)
        with self.assertRaises(ValueError):
            blue_exposure_review(observed_ips="92.119.164.50")


class SolRedTests(unittest.TestCase):
    def test_adversarial_negative_checks_are_isolated(self):
        result = red_isolated_selftest()
        self.assertTrue(result["passed"])
        self.assertFalse(result["network_activity"])
        self.assertEqual(result["attacks_executed"], 0)
        self.assertEqual(len(result["checks"]), 8)

    def test_registration_is_live_but_red_requires_specific_approval(self):
        registry = Selma0ToolRegistryAndroidV1()
        register_sol_security_tools(registry)
        blue = registry.describe("sol.blue.exposure_review")
        red = registry.describe("sol.red.isolated_selftest")
        self.assertTrue(blue["enabled"])
        self.assertTrue(red["enabled"])
        self.assertEqual(blue["risk"], "read")
        self.assertEqual(red["risk"], "sensitive_read")
        engine = Selma0PermissionEngineAndroidV1()
        self.assertFalse(engine.evaluate(red, approved=False).allowed)
        self.assertTrue(engine.evaluate(red, approved=True).allowed)


if __name__ == "__main__":
    unittest.main()
