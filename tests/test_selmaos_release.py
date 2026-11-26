import json
from pathlib import Path
import subprocess
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
ANDROID = "{http://schemas.android.com/apk/res/android}"


class SelmaOSReleaseTests(unittest.TestCase):
    def test_native_shell_is_home_capable_and_permission_minimal(self):
        manifest = ET.parse(
            ROOT / "SELMA0_ANDROID_NATIVE_V1/app/src/main/AndroidManifest.xml"
        ).getroot()
        permissions = [item.get(ANDROID + "name") for item in manifest.findall("uses-permission")]
        self.assertEqual(["android.permission.INTERNET"], permissions)

        application = manifest.find("application")
        self.assertIsNotNone(application)
        self.assertEqual("false", application.get(ANDROID + "allowBackup"))
        self.assertEqual("false", application.get(ANDROID + "usesCleartextTraffic"))
        self.assertEqual("@xml/network_security_config", application.get(ANDROID + "networkSecurityConfig"))

        categories = {
            category.get(ANDROID + "name")
            for activity in application.findall("activity")
            for intent_filter in activity.findall("intent-filter")
            for category in intent_filter.findall("category")
        }
        self.assertIn("android.intent.category.LAUNCHER", categories)
        self.assertIn("android.intent.category.HOME", categories)
        self.assertIn("android.intent.category.DEFAULT", categories)

    def test_android_release_config_and_local_bridge(self):
        gradle = (ROOT / "SELMA0_ANDROID_NATIVE_V1/app/build.gradle").read_text(encoding="utf-8")
        self.assertIn("minSdk 30", gradle)
        self.assertIn("targetSdk 35", gradle)
        self.assertIn("versionName '1.0.0-rc1'", gradle)

        main = (ROOT / "SELMA0_ANDROID_NATIVE_V1/app/src/main/java/ai/selma/companion/MainActivity.java").read_text(encoding="utf-8")
        local = (ROOT / "SELMA0_ANDROID_NATIVE_V1/app/src/main/java/ai/selma/companion/LocalAgentActivity.java").read_text(encoding="utf-8")
        self.assertNotIn("WebView", main)
        self.assertIn("Settings.ACTION_HOME_SETTINGS", main)
        self.assertIn('"http://127.0.0.1:8765', main)
        self.assertIn('payload.put("offline_only", true)', local)
        self.assertNotIn("0.0.0.0", local)

        network = (ROOT / "SELMA0_ANDROID_NATIVE_V1/app/src/main/res/xml/network_security_config.xml").read_text(encoding="utf-8")
        self.assertIn('<base-config cleartextTrafficPermitted="false"', network)
        self.assertIn(">127.0.0.1</domain>", network)

    def test_open_source_apps_are_external_and_curated(self):
        catalog = json.loads((ROOT / "third_party/open_source_apps.json").read_text(encoding="utf-8"))
        self.assertFalse(catalog["policy"]["bundled_apks"])
        self.assertFalse(catalog["policy"]["silent_installation"])
        packages = {app["package_id"] for app in catalog["apps"]}
        self.assertEqual({"com.termux", "org.fdroid.fdroid"}, packages)
        for app in catalog["apps"]:
            self.assertFalse(app["bundled"])
            self.assertEqual("optional_external", app["integration"])
            self.assertTrue(app["source_url"].startswith("https://"))
            self.assertTrue(app["install_url"].startswith("https://"))

    def test_chromeos_installer_is_rootless_and_loopback_only(self):
        directory = ROOT / "SELMAOS_CHROMEOS_V1"
        scripts = [directory / "install.sh", directory / "uninstall.sh", directory / "selmaos-runtime", directory / "selmaos-open"]
        for script in scripts:
            subprocess.run(["bash", "-n", str(script)], check=True, timeout=10)
            contents = script.read_text(encoding="utf-8")
            self.assertNotIn("sudo ", contents)
            self.assertNotIn("0.0.0.0", contents)
        runtime = (directory / "selmaos-runtime").read_text(encoding="utf-8")
        self.assertIn('SELMA0_HOST_V1="127.0.0.1"', runtime)
        self.assertIn("selma0_runtime_command_core_android_v1.py", runtime)

    def test_command_core_defaults_chat_to_offline_only(self):
        command_core = (ROOT / "SELMA0_ANDROID_AGENT_V1/selma0_runtime_command_core_android_v1.py").read_text(encoding="utf-8")
        self.assertIn('body.get("offline_only", True) is True', command_core)
        router = (ROOT / "SELMA0_ANDROID_AGENT_V1/selma0_llm_router_android_v1.py").read_text(encoding="utf-8")
        self.assertIn("ProxyHandler({})", router)
        self.assertIn("_DenyRedirect", router)


if __name__ == "__main__":
    unittest.main()
