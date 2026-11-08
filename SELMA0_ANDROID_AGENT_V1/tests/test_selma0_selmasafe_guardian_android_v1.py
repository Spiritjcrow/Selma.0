import os
import tempfile
import unittest

from selma0_selmasafe_guardian_android_v1 import Selma0SelmaSafeGuardianAndroidV1


class Selma0SelmaSafeGuardianAndroidV1Tests(unittest.TestCase):
    def make_guardian(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        calls = []

        def runner(argv, timeout=12):
            calls.append(list(argv))
            if argv and argv[0] == "termux-microphone-record":
                return {"ok": True, "returncode": 0, "stdout": "Recording started", "stderr": ""}
            return {"ok": False, "returncode": 127, "stdout": "", "stderr": "not available"}

        guardian = Selma0SelmaSafeGuardianAndroidV1(
            profile_path=os.path.join(tmp.name, "profile.json"),
            audit_path=os.path.join(tmp.name, "events.jsonl"),
            selmasafe_base_dir=os.path.join(tmp.name, "selmasafe"),
            selmasafe_runner=runner,
        )
        guardian.profile["include_location_in_sos"] = False
        guardian.profile["send_sms_on_sos"] = False
        guardian._save_profile_v1(guardian.profile)
        return guardian, calls

    def test_confirmed_sos_starts_recording(self):
        guardian, calls = self.make_guardian()
        result = guardian.activate_sos(reason="test", confirmed=True)
        self.assertIn("selmasafe", result)
        self.assertTrue(any(call and call[0] == "termux-microphone-record" for call in calls))

    def test_unconfirmed_sos_does_not_record(self):
        guardian, calls = self.make_guardian()
        with self.assertRaises(ValueError):
            guardian.activate_sos(reason="test", confirmed=False)
        self.assertFalse(calls)

    def test_profile_bounds_recording_limit(self):
        guardian, _ = self.make_guardian()
        profile = guardian.update_profile({"record_limit_seconds": 99999})
        self.assertEqual(profile["record_limit_seconds"], 3600)


if __name__ == "__main__":
    unittest.main()
