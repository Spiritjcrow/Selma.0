"""Source-level launcher guardrails; these do not replace Android lint or device tests."""

import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "SELMA0_ANDROID_NATIVE_V1" / "app" / "src" / "main"
MANIFEST = MAIN / "AndroidManifest.xml"
LAUNCHER = MAIN / "java" / "ai" / "selma" / "companion" / "LauncherActivity.java"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class SelmaLauncherSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ElementTree.parse(MANIFEST).getroot()
        cls.source = LAUNCHER.read_text(encoding="utf-8")

    def test_launcher_is_opt_in_home_and_visible_app_icon(self):
        nodes = [
            a for a in self.root.findall(".//activity")
            if a.attrib.get(ANDROID + "name") == ".LauncherActivity"
        ]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].attrib.get(ANDROID + "exported"), "true")
        filters = nodes[0].findall("intent-filter")
        sets = [
            {c.attrib.get(ANDROID + "name")
             for c in f.findall("category")}
            for f in filters
        ]
        self.assertTrue(any({
            "android.intent.category.HOME", "android.intent.category.DEFAULT"
        }.issubset(s) for s in sets))
        self.assertTrue(any("android.intent.category.LAUNCHER" in s for s in sets))

    def test_existing_cloud_companion_stays_available(self):
        self.assertEqual(len([
            a for a in self.root.findall(".//activity")
            if a.attrib.get(ANDROID + "name") == ".MainActivity"
        ]), 1)

    def test_visibility_is_narrow_and_permissions_are_bounded(self):
        permissions = {
            p.attrib.get(ANDROID + "name")
            for p in self.root.findall("uses-permission")
        }
        self.assertEqual(permissions, {"android.permission.INTERNET"})
        queries = self.root.findall("queries/intent")
        self.assertTrue(any(
            c.attrib.get(ANDROID + "name") == "android.intent.category.LAUNCHER"
            for entry in queries for c in entry.findall("category")
        ))

    def test_real_app_discovery_and_safe_settings_paths(self):
        for marker in (
            "queryIntentActivities", "CATEGORY_LAUNCHER", "startActivity",
            "ACTION_OPEN_DOCUMENT", "ACTION_BLUETOOTH_SETTINGS",
            "Settings.Panel.ACTION_WIFI", "ACTION_HOME_SETTINGS",
            "putStringSet(PINNED", "http://127.0.0.1:8765/"
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        for forbidden in ("QUERY_ALL_PACKAGES", "su -c", "Runtime.getRuntime().exec",
                          "android.permission.WRITE_SECURE_SETTINGS"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
