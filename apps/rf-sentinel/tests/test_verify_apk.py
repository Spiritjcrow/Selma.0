import contextlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest
import zipfile
from unittest import mock


DEFAULT_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "tools" / "verify_apk.py"
)
MODULE_PATH = pathlib.Path(
    os.environ.get("RF_SENTINEL_VERIFY_APK", str(DEFAULT_MODULE_PATH))
)
SPEC = importlib.util.spec_from_file_location("verify_apk", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

EXPECTED_PERMISSIONS = (
    "uses-permission: name='android.permission.ACCESS_WIFI_STATE'\n"
    "uses-permission: name='android.permission.CHANGE_WIFI_STATE'\n"
    "uses-permission: name='android.permission.ACCESS_FINE_LOCATION'\n"
    "uses-permission: name='android.permission.BLUETOOTH'\n"
    "uses-permission: name='android.permission.BLUETOOTH_ADMIN'\n"
    "uses-permission: name='android.permission.BLUETOOTH_SCAN'\n"
)
EXPECTED_BADGING = (
    "sdkVersion:'30'\n"
    "targetSdkVersion:'35'\n"
    "package: name='org.selma.rfsentinel' versionCode='2' "
    "versionName='0.2-source'\n"
    "launchable-activity: name='org.selma.rfsentinel.MainActivity' "
    "label='' icon=''\n"
    "uses-feature-not-required:'android.hardware.wifi'\n"
    "uses-feature-not-required:'android.hardware.bluetooth_le'\n"
)


def synthetic_apk(directory):
    path = pathlib.Path(directory) / "synthetic.apk"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"manifest")
        archive.writestr("classes.dex", b"dex")
    return path


class VerifyApkTests(unittest.TestCase):
    def run_main(
        self,
        apk,
        *,
        aapt2="/sdk/aapt2",
        signer="/sdk/apksigner",
        package_id="org.selma.rfsentinel",
        package_returncode=0,
        permissions=EXPECTED_PERMISSIONS,
        permissions_returncode=0,
        badging=EXPECTED_BADGING,
        badging_returncode=0,
        signer_returncode=0,
    ):
        stdout = io.StringIO()
        stderr = io.StringIO()
        results = [
            mock.Mock(returncode=package_returncode, stdout=package_id),
            mock.Mock(returncode=permissions_returncode, stdout=permissions),
            mock.Mock(returncode=badging_returncode, stdout=badging),
            mock.Mock(returncode=signer_returncode, stdout=""),
        ]

        def find_tool(name):
            return aapt2 if name == "aapt2" else signer

        with mock.patch.object(
            MODULE, "find_build_tool", side_effect=find_tool
        ), mock.patch.object(
            MODULE, "run_tool", side_effect=results
        ) as run, contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(
            stderr
        ):
            code = MODULE.main(["verify_apk.py", str(apk)])
        return code, json.loads(stdout.getvalue()), stderr.getvalue(), run

    def test_verified_artifact_contract_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result, error, run = self.run_main(synthetic_apk(directory))
        self.assertEqual(0, code, error)
        self.assertEqual("PASS", result["archive_test"])
        self.assertEqual("org.selma.rfsentinel", result["package_id"])
        self.assertEqual("ABSENT", result["internet_permission"])
        self.assertEqual("PASS", result["permission_contract"])
        self.assertEqual("30", result["min_sdk"])
        self.assertEqual("35", result["target_sdk"])
        self.assertEqual(
            "org.selma.rfsentinel.MainActivity",
            result["launchable_activity"],
        )
        self.assertEqual("PASS", result["radio_hardware_optional"])
        self.assertEqual("2", result["version_code"])
        self.assertEqual("0.2-source", result["version_name"])
        self.assertEqual("PASS", result["signature"])
        self.assertEqual(4, run.call_count)

    def test_missing_aapt2_blocks_instead_of_claiming_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result, error, run = self.run_main(
                synthetic_apk(directory), aapt2=None
            )
        self.assertEqual(75, code)
        self.assertEqual("BLOCKED", result["package_id"])
        self.assertIn("AAPT2 is required", error)
        run.assert_not_called()

    def test_missing_apksigner_blocks_instead_of_claiming_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result, error, run = self.run_main(
                synthetic_apk(directory), signer=None
            )
        self.assertEqual(75, code)
        self.assertEqual("BLOCKED", result["signature"])
        self.assertIn("apksigner is required", error)
        self.assertEqual(3, run.call_count)

    def test_invalid_signature_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result, _, _ = self.run_main(
                synthetic_apk(directory), signer_returncode=1
            )
        self.assertEqual(1, code)
        self.assertEqual("FAIL", result["signature"])

    def test_wrong_package_fails_before_other_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result, error, run = self.run_main(
                synthetic_apk(directory), package_id="example.wrong"
            )
        self.assertEqual(1, code)
        self.assertEqual("example.wrong", result["package_id"])
        self.assertIn("unexpected APK package identity", error)
        self.assertEqual(1, run.call_count)

    def test_permission_contract_failures(self):
        cases = {
            "dump-error": {
                "permissions_returncode": 1,
                "expected": "could not read APK permissions",
            },
            "internet": {
                "permissions": EXPECTED_PERMISSIONS
                + "uses-permission: name='android.permission.INTERNET'\n",
                "expected": "violates offline-first policy",
            },
            "missing-reviewed": {
                "permissions": EXPECTED_PERMISSIONS.replace(
                    "uses-permission: name='android.permission.ACCESS_FINE_LOCATION'\n",
                    "",
                ),
                "expected": "differs from reviewed contract",
            },
            "unexpected": {
                "permissions": EXPECTED_PERMISSIONS
                + "uses-permission: name='android.permission.RECORD_AUDIO'\n",
                "expected": "differs from reviewed contract",
            },
        }
        for name, values in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                expected = values.pop("expected")
                code, _, error, run = self.run_main(
                    synthetic_apk(directory), **values
                )
                self.assertEqual(1, code)
                self.assertIn(expected, error)
                self.assertEqual(2, run.call_count)

    def test_packaged_manifest_contract_failures(self):
        sdk = "sdkVersion:'30'\ntargetSdkVersion:'35'\n"
        launcher = (
            "launchable-activity: name='org.selma.rfsentinel.MainActivity' "
            "label='' icon=''\n"
        )
        features = (
            "uses-feature-not-required:'android.hardware.wifi'\n"
            "uses-feature-not-required:'android.hardware.bluetooth_le'\n"
        )
        version = (
            "package: name='org.selma.rfsentinel' versionCode='2' "
            "versionName='0.2-source'\n"
        )
        cases = {
            "dump-error": {
                "badging_returncode": 1,
                "expected": "could not read APK SDK compatibility",
            },
            "missing-sdk": {
                "badging": "sdkVersion:'30'\n",
                "expected": "compatibility evidence is incomplete",
            },
            "wrong-min-sdk": {
                "badging": "sdkVersion:'29'\ntargetSdkVersion:'35'\n",
                "expected": "unexpected APK SDK compatibility",
            },
            "wrong-target-sdk": {
                "badging": "sdkVersion:'30'\ntargetSdkVersion:'34'\n",
                "expected": "unexpected APK SDK compatibility",
            },
            "missing-launcher": {
                "badging": sdk,
                "expected": "no verified launchable activity",
            },
            "wrong-launcher": {
                "badging": sdk
                + "launchable-activity: name='example.WrongActivity' label='' icon=''\n",
                "expected": "unexpected APK launchable activity",
            },
            "missing-optional-feature": {
                "badging": sdk + launcher,
                "expected": "does not preserve optional radio hardware",
            },
            "required-radio-feature": {
                "badging": sdk
                + launcher
                + "uses-feature:'android.hardware.wifi'\n"
                + features,
                "expected": "does not preserve optional radio hardware",
            },
            "missing-version": {
                "badging": sdk + launcher + features,
                "expected": "version evidence is incomplete",
            },
            "wrong-version": {
                "badging": sdk
                + launcher
                + features
                + "package: name='org.selma.rfsentinel' versionCode='3' "
                "versionName='0.3-source'\n",
                "expected": "unexpected APK version metadata",
            },
        }
        for name, values in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                expected = values.pop("expected")
                code, _, error, run = self.run_main(
                    synthetic_apk(directory), **values
                )
                self.assertEqual(1, code)
                self.assertIn(expected, error)
                self.assertEqual(3, run.call_count)


if __name__ == "__main__":
    unittest.main()
