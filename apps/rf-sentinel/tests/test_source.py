import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ProjectContracts(unittest.TestCase):
    def test_no_network_permission(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text()
        self.assertNotIn("android.permission.INTERNET", manifest)
        self.assertIn("android.permission.BLUETOOTH_SCAN", manifest)
        self.assertIn("android.permission.ACCESS_FINE_LOCATION", manifest)

    def test_user_initiated_survey(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        for action in ("SCAN WI-FI", "SCAN BLE", "STOP BLE", "EXPORT CSV"):
            self.assertIn(action, code)
        self.assertNotIn("startForegroundService(", code)
        self.assertNotIn("TelephonyManager", code)

    def test_no_danger_inference(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/RfMetrics.kt").read_text()
        self.assertIn("radio change index", code)
        self.assertNotIn("attackProbability", code)

    def test_optional_wifi_hardware_fails_closed(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        self.assertIn("private var wifiManager: WifiManager? = null", code)
        self.assertIn("Wi-Fi hardware unavailable.", code)
        self.assertNotIn("as WifiManager", code)

    def test_main_activity_source_is_complete(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        self.assertIn("private fun exportCsv()", code)
        self.assertIn("override fun onDestroy()", code)
        self.assertTrue(code.rstrip().endswith("}"))

if __name__ == "__main__":
    unittest.main()

