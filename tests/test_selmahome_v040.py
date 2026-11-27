import hashlib
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
HOME = ROOT / "SELMAHOME_ANDROID_V040"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class SelmaHomeV040Tests(unittest.TestCase):
    def test_manifest_is_home_capable_and_permission_bounded(self):
        manifest = ET.parse(HOME / "AndroidManifest.xml").getroot()
        self.assertEqual("org.selma.home", manifest.get("package"))
        self.assertEqual("5", manifest.get(ANDROID + "versionCode"))
        self.assertEqual("0.4.0", manifest.get(ANDROID + "versionName"))
        sdk = manifest.find("uses-sdk")
        self.assertEqual("29", sdk.get(ANDROID + "minSdkVersion"))
        self.assertEqual("35", sdk.get(ANDROID + "targetSdkVersion"))
        permissions = sorted(node.get(ANDROID + "name") for node in manifest.findall("uses-permission"))
        self.assertEqual(
            ["android.permission.INTERNET", "android.permission.RECEIVE_BOOT_COMPLETED"],
            permissions,
        )
        categories = {
            item.get(ANDROID + "name")
            for item in manifest.findall(".//category")
        }
        self.assertTrue(
            {"android.intent.category.DEFAULT", "android.intent.category.HOME", "android.intent.category.LAUNCHER"}.issubset(categories)
        )

    def test_model_digests_and_embedded_license(self):
        for line in (HOME / "assets.sha256").read_text(encoding="utf-8").splitlines():
            expected, relative = line.split(maxsplit=1)
            path = HOME / relative
            if path.is_file():
                payload = path.read_bytes()
            else:
                self.assertEqual("assets/model.bin", relative)
                payload = b"".join(path.read_bytes() for path in sorted((HOME / "model").glob("model.bin.part*")))
            self.assertEqual(expected, hashlib.sha256(payload).hexdigest())
        self.assertEqual(
            (HOME / "MODEL-LICENSE.txt").read_bytes(),
            (HOME / "assets/licenses/tinyllamas-MIT.txt").read_bytes(),
        )

    def test_mcp_is_loopback_authenticated_and_bounded(self):
        source = (HOME / "src/org/selma/home/ToolServer.java").read_text(encoding="utf-8")
        self.assertIn('InetAddress.getByName("127.0.0.1")', source)
        self.assertIn('("Bearer "+secret).equals', source)
        self.assertIn('headers.containsKey("origin")', source)
        self.assertIn('size>16384', source)
        self.assertNotIn("0.0.0.0", source)
        java = "\n".join(path.read_text(encoding="utf-8") for path in (HOME / "src").rglob("*.java"))
        self.assertNotIn("WebView", java)
        self.assertNotRegex(java, r'https?://(?!127\.0\.0\.1)')

    def test_release_build_does_not_embed_signing_material(self):
        script = (HOME / "build-host.sh").read_text(encoding="utf-8")
        self.assertIn("SELMA_KEYSTORE", script)
        self.assertIn("SELMA_KEYPASS_FILE", script)
        self.assertIn("apksigner", script)
        self.assertIn("zipalign", script)
        self.assertFalse(any(HOME.rglob("*.p12")))
        self.assertFalse(any(HOME.rglob("*.jks")))


if __name__ == "__main__":
    unittest.main()
