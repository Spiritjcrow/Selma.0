import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class TestSetup(unittest.TestCase):
    def test_recommendation_unknown_fails_safe(self):
        self.assertEqual(setup.recommended_profile({"available_ram_mb": None}), "eco")
        self.assertEqual(setup.recommended_profile({"available_ram_mb": 2048}), "eco")
        self.assertEqual(setup.recommended_profile({"available_ram_mb": 4000}), "balanced")

    def test_allowlist_and_local_only(self):
        prefs = setup.checked_preferences({"profile": "eco", "scene": "coast", "motion": "reduced"})
        self.assertFalse(prefs["autogrant_permissions"])
        self.assertFalse(prefs["model_installed"])
        self.assertEqual(prefs["network"], "local_only")
        with self.assertRaises(ValueError):
            setup.checked_preferences({"profile": "eco", "scene": "coast", "motion": "normal", "api_key": "secret"})
        with self.assertRaises(ValueError):
            setup.checked_preferences({"profile": "ultra", "scene": "coast", "motion": "normal"})

    def test_permissions_on_disk(self):
        with tempfile.TemporaryDirectory() as t:
            file = Path(t) / "prefs.json"
            setup.save_preferences({"profile": "eco", "scene": "forest", "motion": "normal"}, file)
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(__import__("json").loads(file.read_text())["scene"], "forest")


if __name__ == "__main__":
    unittest.main()
