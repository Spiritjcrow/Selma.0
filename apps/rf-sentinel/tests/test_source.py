import os
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = pathlib.Path(os.environ.get("RF_SENTINEL_REPO_ROOT", ROOT.parents[1]))

class ProjectContracts(unittest.TestCase):
    def test_no_network_permission(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text()
        self.assertNotIn("android.permission.INTERNET", manifest)
        self.assertIn("android.permission.BLUETOOTH_SCAN", manifest)
        self.assertIn("android.permission.ACCESS_COARSE_LOCATION", manifest)
        self.assertNotIn("android.permission.BLUETOOTH_CONNECT", manifest)
        self.assertIn("android.permission.ACCESS_FINE_LOCATION", manifest)

    def test_precise_location_is_requested_with_coarse_location(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        helper = code[
            code.index("private fun locationPermissions"):
            code.index("private fun withPermissions")
        ]
        self.assertIn("Manifest.permission.ACCESS_COARSE_LOCATION", helper)
        self.assertIn("Manifest.permission.ACCESS_FINE_LOCATION", helper)
        on_create = code[code.index("override fun onCreate"):code.index("override fun onStart")]
        self.assertIn("withPermissions(locationPermissions()) { startWifi() }", on_create)
        self.assertIn("else locationPermissions()", on_create)

    def test_user_initiated_survey(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        for action in ("SCAN WI-FI", "SCAN BLE", "STOP BLE", "EXPORT CSV"):
            self.assertIn(action, code)
        self.assertNotIn("startForegroundService(", code)
        self.assertNotIn("TelephonyManager", code)

    def test_permission_result_cannot_start_scan_offscreen(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        self.assertIn("private var activityStarted = false", code)
        self.assertIn("override fun onStart()", code)
        self.assertIn("activityStarted = true", code)
        callback = code[
            code.index("override fun onRequestPermissionsResult"):
            code.index("@Suppress(\"DEPRECATION\")", code.index("override fun onRequestPermissionsResult"))
        ]
        self.assertIn("if (!activityStarted)", callback)
        on_stop = code[
            code.index("override fun onStop()"):
            code.index("override fun onDestroy()")
        ]
        self.assertLess(
            on_stop.index("activityStarted = false"),
            on_stop.index("pendingAction = null"),
        )
        self.assertLess(
            on_stop.index("pendingAction = null"),
            on_stop.index("stopBle(recordResults = false)"),
        )

    def test_wifi_results_cannot_be_recorded_offscreen(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        receiver = code[
            code.index("private val wifiReceiver"):
            code.index("private val bleCallback")
        ]
        self.assertIn("if (!activityStarted) return", receiver)
        self.assertLess(
            receiver.index("if (!activityStarted) return"),
            receiver.index("readWifi("),
        )
        read_wifi = code[
            code.index("private fun readWifi"):
            code.index("private fun startBle")
        ]
        self.assertIn("if (!activityStarted)", read_wifi)
        self.assertLess(
            read_wifi.index("if (!activityStarted)"),
            read_wifi.index("manager.scanResults"),
        )

    def test_wifi_receiver_is_non_exported_on_android_13_plus(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        registration = code[
            code.index("private fun registerWifiReceiver"):
            code.index("private fun withPermissions")
        ]
        self.assertIn("Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU", registration)
        self.assertIn("Context.RECEIVER_NOT_EXPORTED", registration)
        self.assertEqual(registration.count("registerReceiver(wifiReceiver, filter"), 2)
        on_create = code[code.index("override fun onCreate"):code.index("override fun onStart")]
        self.assertIn("registerWifiReceiver()", on_create)

    def test_activity_stop_discards_partial_ble_scan(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        stop_ble = code[
            code.index("private fun stopBle"):
            code.index("private fun snapshot")
        ]
        self.assertIn("private fun stopBle(recordResults: Boolean = true)", stop_ble)
        self.assertIn("if (!recordResults)", stop_ble)
        self.assertLess(
            stop_ble.index("if (!recordResults)"),
            stop_ble.index("bleCount = bleSamples.size"),
        )
        self.assertLess(
            stop_ble.index("if (!recordResults)"),
            stop_ble.index("saveRow()"),
        )
        on_stop = code[
            code.index("override fun onStop()"):
            code.index("override fun onDestroy()")
        ]
        self.assertIn("stopBle(recordResults = false)", on_stop)

    def test_stale_ble_failure_callback_is_ignored(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        callback = code[
            code.index("override fun onScanFailed"):
            code.index("override fun onCreate")
        ]
        guard = "if (!activityStarted || !scanningBle) return"
        self.assertIn(guard, callback)
        self.assertLess(callback.index(guard), callback.index("scanningBle = false"))
        self.assertLess(callback.index(guard), callback.index("render()"))

    def test_ble_device_keys_are_erased_when_scan_ends(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        failed = code[
            code.index("override fun onScanFailed"):
            code.index("override fun onCreate")
        ]
        self.assertIn("bleSamples.clear()", failed)
        self.assertLess(failed.index("bleSamples.clear()"), failed.index("render()"))

        stop_ble = code[
            code.index("private fun stopBle"):
            code.index("private fun snapshot")
        ]
        aggregate_end = stop_ble.index("bleMean =")
        save_row = stop_ble.index("saveRow()")
        clear_after_aggregate = stop_ble.index("bleSamples.clear()", aggregate_end)
        self.assertLess(clear_after_aggregate, save_row)

    def test_ble_start_failures_release_scanner_state(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        start_ble = code[
            code.index("private fun startBle"):
            code.index("private fun abortBleStart")
        ]
        self.assertEqual(start_ble.count("abortBleStart("), 2)

        abort = code[
            code.index("private fun abortBleStart"):
            code.index("private fun stopBle(recordResults")
        ]
        for statement in (
            "handler.removeCallbacks(stopTask)",
            "scanningBle = false",
            "stopBleScannerSafely()",
            "scanner = null",
            "bleSamples.clear()",
        ):
            self.assertIn(statement, abort)
        self.assertLess(abort.index("stopBleScannerSafely()"), abort.index("scanner = null"))
        self.assertLess(abort.index("bleSamples.clear()"), abort.index("render()"))

    def test_ble_scan_calls_are_permission_checked_without_connect_scope(self):
        code = (ROOT / "app/src/main/java/org/selma/rfsentinel/MainActivity.kt").read_text()
        self.assertNotIn("BluetoothManager", code)
        start = code[
            code.index("private fun startBle"):
            code.index("private fun stopBleScannerSafely")
        ]
        permission_check = "checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)"
        self.assertIn(permission_check, start)
        self.assertLess(start.index(permission_check), start.index("active.startScan("))

        stop = code[
            code.index("private fun stopBleScannerSafely"):
            code.index("private fun abortBleStart")
        ]
        self.assertIn(permission_check, stop)
        self.assertLess(stop.index(permission_check), stop.index("active.stopScan(bleCallback)"))
        self.assertIn("catch (_: SecurityException)", stop)
        self.assertEqual(code.count("stopScan(bleCallback)"), 1)

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

    def test_ci_verifies_apk_before_hash_and_upload(self):
        workflow = (REPO_ROOT / ".github/workflows/rf-sentinel-ci.yml").read_text()
        verify = "python3 tools/verify_apk.py app/build/outputs/apk/debug/app-debug.apk"
        sha256 = "sha256sum app/build/outputs/apk/debug/app-debug.apk"
        upload = "uses: actions/upload-artifact@v4"
        self.assertIn(verify, workflow)
        self.assertLess(workflow.index(verify), workflow.index(sha256))
        self.assertLess(workflow.index(verify), workflow.index(upload))

    def test_ci_requires_android_gates_before_apk_verification(self):
        workflow = (REPO_ROOT / ".github/workflows/rf-sentinel-ci.yml").read_text()
        gates = "gradle --no-daemon :app:lintDebug :app:testDebugUnitTest :app:assembleDebug"
        verify = "python3 tools/verify_apk.py app/build/outputs/apk/debug/app-debug.apk"
        self.assertIn(gates, workflow)
        self.assertLess(workflow.index(gates), workflow.index(verify))

    def test_ci_artifact_bundles_apk_hash_and_verification(self):
        workflow = (REPO_ROOT / ".github/workflows/rf-sentinel-ci.yml").read_text()
        apk = "apps/rf-sentinel/app/build/outputs/apk/debug/app-debug.apk"
        checksum = apk + ".sha256"
        verification = (
            "apps/rf-sentinel/app/build/outputs/apk/debug/"
            "rf-sentinel-debug-verification.json"
        )
        self.assertIn("| tee app/build/outputs/apk/debug/rf-sentinel-debug-verification.json", workflow)
        self.assertIn("sha256sum app/build/outputs/apk/debug/app-debug.apk", workflow)
        self.assertIn("> app/build/outputs/apk/debug/app-debug.apk.sha256", workflow)
        for artifact in (apk, checksum, verification):
            self.assertIn(artifact, workflow)

if __name__ == "__main__":
    unittest.main()


