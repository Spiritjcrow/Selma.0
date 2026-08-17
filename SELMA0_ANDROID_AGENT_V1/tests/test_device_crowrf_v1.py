#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_crowrf_wifi_scan_android_v1 import (
    collect_crowrf_wifi_scan_v1,
    normalize_wifi_scan_record_v1,
    register_crowrf_tools,
)
from selma0_device_bridge_android_v1 import (
    Selma0TermuxDeviceBridgeAndroidV1,
    register_device_tools,
)
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1


class FakeRunner:
    def __init__(self, stdout="{}", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return SimpleNamespace(
            stdout=self.stdout,
            stderr=self.stderr,
            returncode=self.returncode,
        )


class FakeScanBridge:
    def __init__(self, payload):
        self.payload = payload

    def read_json(self, operation):
        if operation != "wifi_scan":
            raise AssertionError(f"unexpected operation: {operation}")
        return {
            "ok": True,
            "source": "termux-api:termux-wifi-scaninfo",
            "measurement_kind": "measured",
            "device_local": True,
            "collected_at": "2026-08-17T00:00:00+00:00",
            "command": "termux-wifi-scaninfo",
            "data": self.payload,
        }


class DeviceBridgeTests(unittest.TestCase):
    def _bridge(self, runner):
        return Selma0TermuxDeviceBridgeAndroidV1(
            runner=runner,
            which=lambda name: f"/data/data/com.termux/files/usr/bin/{name}",
            timeout_seconds=3,
        )

    def test_only_allowlisted_read_operations_are_exposed(self):
        bridge = self._bridge(FakeRunner())
        with self.assertRaises(ValueError):
            bridge.read_json("shell")

    def test_wifi_scan_runs_without_shell_and_parses_json(self):
        runner = FakeRunner(stdout=json.dumps([{"ssid": "lab", "level": -48}]))
        bridge = self._bridge(runner)
        result = bridge.read_json("wifi_scan")
        self.assertTrue(result["ok"])
        self.assertEqual(result["measurement_kind"], "measured")
        self.assertEqual(result["data"][0]["level"], -48)
        command, kwargs = runner.calls[0]
        self.assertTrue(command[0].endswith("termux-wifi-scaninfo"))
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 3)

    def test_missing_termux_command_fails_without_fake_data(self):
        bridge = Selma0TermuxDeviceBridgeAndroidV1(
            runner=FakeRunner(),
            which=lambda _name: None,
        )
        with self.assertRaises(RuntimeError):
            bridge.read_json("wifi_scan")

    def test_invalid_json_fails_closed(self):
        bridge = self._bridge(FakeRunner(stdout="not-json"))
        with self.assertRaises(RuntimeError):
            bridge.read_json("wifi_scan")

    def test_effect_commands_are_bounded(self):
        runner = FakeRunner(stdout="")
        bridge = self._bridge(runner)
        bridge.vibrate(duration_ms=999999)
        command, kwargs = runner.calls[-1]
        self.assertEqual(command[-2:], ["-d", "5000"])
        self.assertIs(kwargs["shell"], False)


class CrowRFTests(unittest.TestCase):
    def test_normalizer_preserves_raw_measurement(self):
        raw = {
            "SSID": "selma-lab",
            "BSSID": "02:00:00:00:00:01",
            "frequency": 5180,
            "level": -55,
            "capabilities": "[WPA2-PSK-CCMP][ESS]",
        }
        record = normalize_wifi_scan_record_v1(raw)
        self.assertEqual(record["ssid"], "selma-lab")
        self.assertEqual(record["frequency_mhz"], 5180)
        self.assertEqual(record["rssi_dbm"], -55)
        self.assertEqual(record["raw"], raw)

    def test_scan_is_measured_and_contains_no_invented_inference(self):
        scan = collect_crowrf_wifi_scan_v1(
            bridge=FakeScanBridge(
                [
                    {
                        "ssid": "ap-1",
                        "bssid": "aa:bb:cc:dd:ee:ff",
                        "frequency": 2412,
                        "level": -62,
                    }
                ]
            )
        )
        self.assertEqual(scan["measurement_kind"], "measured")
        self.assertEqual(scan["record_count"], 1)
        self.assertIsNone(scan["inference"])
        self.assertFalse(scan["limitations"]["csi_available"])
        self.assertFalse(scan["limitations"]["geometry_measured"])
        self.assertFalse(scan["limitations"]["distance_estimated"])

    def test_empty_scan_stays_empty(self):
        scan = collect_crowrf_wifi_scan_v1(bridge=FakeScanBridge([]))
        self.assertEqual(scan["record_count"], 0)
        self.assertEqual(scan["records"], [])

    def test_non_array_scan_output_is_rejected(self):
        with self.assertRaises(RuntimeError):
            collect_crowrf_wifi_scan_v1(bridge=FakeScanBridge({"ssid": "not-an-array"}))

    def test_tool_risk_classes_match_command_policy(self):
        registry = Selma0ToolRegistryAndroidV1()
        bridge = self._bridge_for_registration()
        register_device_tools(registry, bridge=bridge)
        register_crowrf_tools(registry, bridge=bridge)
        self.assertEqual(registry.describe("device.battery_status")["risk"], "read")
        self.assertEqual(registry.describe("device.wifi_connection")["risk"], "read")
        self.assertEqual(registry.describe("device.location")["risk"], "sensitive_read")
        self.assertEqual(registry.describe("device.notify")["risk"], "external_effect")
        self.assertEqual(registry.describe("device.vibrate")["risk"], "external_effect")
        self.assertEqual(registry.describe("crowrf.wifi_scan")["risk"], "read")

    @staticmethod
    def _bridge_for_registration():
        return Selma0TermuxDeviceBridgeAndroidV1(
            runner=FakeRunner(),
            which=lambda name: f"/termux/{name}",
        )


if __name__ == "__main__":
    unittest.main()
