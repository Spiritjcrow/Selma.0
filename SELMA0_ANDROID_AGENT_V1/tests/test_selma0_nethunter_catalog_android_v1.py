import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import selma0_nethunter_catalog_android_v1 as catalog
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1


class NetHunterCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache_patch = patch.object(catalog, "CACHE_FILE", Path(self.tmp.name) / "data" / "catalog.json")
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.fixture = {
            "apps": [
                {"packageName": "com.termux", "name": "Termux",
                 "summary": "Terminal emulator", "categories": ["System"]},
                {"packageName": "com.example.tool", "name": "Test Tool",
                 "summary": "Fixture only", "categories": ["Forensics"]},
            ],
            "packages": {
                "com.termux": [
                    {"versionName": "0.1", "versionCode": 1, "minSdkVersion": 21},
                    {"versionName": "0.2", "versionCode": 2, "minSdkVersion": 24}
                ]
            },
        }

    def test_sync_and_search_are_metadata_only(self):
        with patch.object(catalog, "_download_index", return_value=self.fixture):
            synced = catalog.sync_catalog()
        self.assertEqual(synced["count"], 2)
        self.assertFalse(synced["installed"])
        self.assertEqual(synced["executors_created"], 0)
        all_apps = catalog.list_catalog()
        self.assertEqual(all_apps["count"], 2)
        self.assertEqual(catalog.list_catalog("terminal")["count"], 1)
        details = catalog.package_details("com.termux")
        self.assertEqual(details["app"]["version"], "0.2")
        self.assertEqual(details["app"]["store_page"],
                         "https://store.nethunter.com/packages/com.termux/")

    def test_malformed_index_rejected_without_writing(self):
        with patch.object(catalog, "_download_index", return_value={"apps": "wrong"}):
            with self.assertRaises(ValueError):
                catalog.sync_catalog()
        self.assertFalse(catalog.CACHE_FILE.exists())

    def test_package_ids_not_used_as_urls_without_validation(self):
        with self.assertRaises(ValueError):
            catalog.package_details("../malicious")
        with self.assertRaises(ValueError):
            catalog.package_details("http://example.com")

    def test_registry_exposes_only_bounded_operations(self):
        registry = Selma0ToolRegistryAndroidV1()
        catalog.register_nethunter_catalog_tools(registry)
        self.assertEqual(registry.describe("nethunter.catalog_sync")["risk"],
                         "external_effect")
        self.assertEqual(registry.describe("nethunter.catalog")["risk"], "read")
        self.assertEqual(len(registry.list_public()), 3)
        self.assertFalse(any("execute" in entry["name"] or "install" in entry["name"]
                             for entry in registry.list_public()))


if __name__ == "__main__":
    unittest.main()
