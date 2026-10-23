#!/usr/bin/env python3
"""Source-level contract tests only, not proof of APK compilation or device behavior."""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NATIVE = REPO / "SELMA0_ANDROID_NATIVE_V1" / "app" / "src" / "main"


class NativeOfflineContractTests(unittest.TestCase):
    def test_chat_screen_requests_strict_offline_mode(self):
        screen = (NATIVE / "java/ai/selma/companion/LocalAgentActivity.java").read_text()
        self.assertIn('payload.put("offline_only", true)', screen)
        self.assertIn('result.optBoolean("offline_only_supported", false)', screen)
        self.assertIn('result.optBoolean("local_llm_loopback", false)', screen)
        self.assertIn('send.setEnabled(false)', screen)
        self.assertIn('http://127.0.0.1:8765', screen)
        self.assertNotIn('http://0.0.0.0:', screen)

    def test_only_internet_permission_declared(self):
        manifest = (NATIVE / "AndroidManifest.xml").read_text()
        self.assertEqual(manifest.count("<uses-permission"), 1)
        self.assertIn('android.permission.INTERNET', manifest)
        self.assertIn('android:exported="false"', manifest)
        self.assertIn('@xml/network_security_config', manifest)

    def test_cleartext_is_scoped_to_loopback(self):
        network = (NATIVE / "res/xml/network_security_config.xml").read_text()
        self.assertIn('<base-config cleartextTrafficPermitted="false"', network)
        self.assertIn('<domain includeSubdomains="false">127.0.0.1</domain>', network)
        self.assertNotIn('<domain includeSubdomains="true">', network)

    def test_cloud_mode_requires_explicit_tap(self):
        screen = (NATIVE / "java/ai/selma/companion/MainActivity.java").read_text()
        self.assertIn('cloud.setOnClickListener(v -> openOnline())', screen)
        self.assertIn('request::deny', screen)


if __name__ == "__main__":
    unittest.main()
