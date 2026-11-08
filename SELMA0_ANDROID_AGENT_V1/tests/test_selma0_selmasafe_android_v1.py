import json
import os
import tempfile
import time
import unittest

from selma0_selmasafe_android_v1 import Selma0SelmaSafeAndroidV1


class Selma0SelmaSafeAndroidV1Tests(unittest.TestCase):
    def make_safe(self, runner=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Selma0SelmaSafeAndroidV1(runner=runner, base_dir=tmp.name)

    def test_enrollment_uses_selmasafe_id_not_imei(self):
        safe = self.make_safe()
        device = safe.enroll_device("Family phone", role="family")
        self.assertTrue(device["device_id"])
        self.assertNotIn("imei", device)
        self.assertEqual(len(safe.list_devices()), 1)

    def test_unsigned_fanout_fails_closed(self):
        old = os.environ.pop("SELMA0_SAFE_SHARED_SECRET_V1", None)
        self.addCleanup(lambda: old is not None and os.environ.__setitem__("SELMA0_SAFE_SHARED_SECRET_V1", old))
        safe = self.make_safe()
        safe.enroll_device("Peer")
        result = safe.queue_sos_fanout("test")
        self.assertFalse(result["ok"])
        self.assertIn("shared secret", result["error"])

    def test_signed_envelope_verifies_and_expires(self):
        old = os.environ.get("SELMA0_SAFE_SHARED_SECRET_V1")
        os.environ["SELMA0_SAFE_SHARED_SECRET_V1"] = "test-secret"
        self.addCleanup(lambda: os.environ.__setitem__("SELMA0_SAFE_SHARED_SECRET_V1", old) if old is not None else os.environ.pop("SELMA0_SAFE_SHARED_SECRET_V1", None))
        safe = self.make_safe()
        envelope = safe.build_sos_envelope("test", ttl_seconds=30)
        verified = safe.verify_envelope(envelope, now=envelope["payload"]["issued_unix"] + 1)
        self.assertTrue(verified["ok"])
        expired = safe.verify_envelope(envelope, now=envelope["payload"]["expires_unix"] + 1)
        self.assertFalse(expired["ok"])

    def test_recording_command_is_bounded(self):
        calls = []
        def runner(argv, timeout=12):
            calls.append((list(argv), timeout))
            return {"ok": True, "stdout": "Recording started", "stderr": "", "returncode": 0}
        safe = self.make_safe(runner=runner)
        result = safe.start_audio_recording(limit_seconds=99999)
        self.assertTrue(result["ok"])
        self.assertEqual(result["limit_seconds"], 3600)
        argv = calls[0][0]
        self.assertEqual(argv[0], "termux-microphone-record")
        self.assertIn("-f", argv)
        self.assertIn("-l", argv)

    def test_inactivity_never_auto_deletes(self):
        safe = self.make_safe()
        state = safe.check_in()
        future = state["last_check_in_unix"] + 8 * 24 * 60 * 60
        result = safe.evaluate_inactivity(now=future)
        self.assertEqual(result["state"], "locked_pending_verification")
        self.assertFalse(result["destructive_action"])
        self.assertFalse(result["destructive_auto_delete"])


if __name__ == "__main__":
    unittest.main()
