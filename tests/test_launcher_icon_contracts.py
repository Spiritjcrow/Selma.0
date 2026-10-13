"""Verify packaged Android launcher vector icons and manifest wiring.

These are source checks, not evidence of an assembled APK or device install.
"""

import unittest
from pathlib import Path
from xml.etree import ElementTree

ANDROID = "{http://schemas.android.com/apk/res/android}"
ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "SELMA0_ANDROID_NATIVE_V1" / "app" / "src" / "main"
DRAWABLE = MAIN / "res" / "drawable"


class LauncherIconContractTests(unittest.TestCase):
    def test_both_launcher_entry_points_reference_packaged_icons(self):
        root = ElementTree.parse(MAIN / "AndroidManifest.xml").getroot()
        app = root.find("application")
        self.assertIsNotNone(app)
        self.assertEqual(app.attrib.get(ANDROID + "icon"), "@drawable/ic_selma")
        self.assertEqual(app.attrib.get(ANDROID + "roundIcon"), "@drawable/ic_selma")
        activities = {
            a.attrib.get(ANDROID + "name"): a
            for a in app.findall("activity")
        }
        self.assertIn(".MainActivity", activities)
        self.assertIn(".LauncherActivity", activities)
        self.assertEqual(
            activities[".LauncherActivity"].attrib.get(ANDROID + "icon"),
            "@drawable/ic_selma_home",
        )

    def test_both_icons_are_valid_standalone_vectors(self):
        for name in ("ic_selma", "ic_selma_home"):
            with self.subTest(name=name):
                xml = DRAWABLE / (name + ".xml")
                self.assertTrue(xml.is_file(), str(xml))
                root = ElementTree.parse(xml).getroot()
                self.assertEqual(root.tag, "vector")
                self.assertEqual(root.attrib.get(ANDROID + "width"), "108dp")
                self.assertEqual(root.attrib.get(ANDROID + "height"), "108dp")
                self.assertEqual(root.attrib.get(ANDROID + "viewportWidth"), "108")
                self.assertEqual(root.attrib.get(ANDROID + "viewportHeight"), "108")
                paths = root.findall("path")
                self.assertGreaterEqual(len(paths), 3)
                for path in paths:
                    self.assertTrue(path.attrib.get(ANDROID + "pathData"))
                    self.assertTrue(
                        path.attrib.get(ANDROID + "fillColor")
                        or path.attrib.get(ANDROID + "strokeColor")
                    )
                self.assertNotIn("http://", xml.read_text(encoding="utf-8").split("-->", 1)[-1])

    def test_home_icon_is_distinct_from_companion_icon(self):
        self.assertNotEqual(
            (DRAWABLE / "ic_selma.xml").read_bytes(),
            (DRAWABLE / "ic_selma_home.xml").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
