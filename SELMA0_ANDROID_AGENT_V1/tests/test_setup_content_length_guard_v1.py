"""Synthetic HTTP header-framing checks for the local first-run wizard.

No socket, Android device, external host, or runtime process is started.
"""
import io
import json
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup


class TestContentLengthGuard(unittest.TestCase):
    @staticmethod
    def handler_with_lengths(*lengths):
        options = {"profile": "eco", "scene": "coast", "motion": "reduced"}
        raw = json.dumps(options).encode("utf-8")
        handler = object.__new__(setup.WizardHandler)
        handler.path = "/start"
        headers = Message()
        headers.add_header("Host", "127.0.0.1:8766")
        headers.add_header("X-Selma-Setup-Token", setup.TOKEN)
        headers.add_header("Content-Type", "application/json")
        for value in lengths:
            headers.add_header("Content-Length", value)
        handler.headers = headers
        handler.rfile = io.BytesIO(raw)
        replies = []
        handler.reply = lambda code, payload: replies.append((code, payload))
        return handler, replies, len(raw)

    def assert_rejected_before_side_effects(self, *lengths):
        handler, replies, _ = self.handler_with_lengths(*lengths)
        with mock.patch.object(setup, "save_preferences") as save, \
             mock.patch.object(setup.subprocess, "Popen") as spawn:
            handler.do_POST()
        self.assertEqual(replies, [(400, {"error": "invalid request size"})])
        save.assert_not_called()
        spawn.assert_not_called()

    def test_duplicate_identical_and_conflicting_lengths_rejected(self):
        _, _, length = self.handler_with_lengths()
        for pair in ((str(length), str(length)), (str(length), "1")):
            with self.subTest(pair=pair):
                self.assert_rejected_before_side_effects(*pair)

    def test_signed_or_whitespace_prefixed_length_rejected(self):
        _, _, length = self.handler_with_lengths()
        for raw in ("+" + str(length), " " + str(length), "-" + str(length)):
            with self.subTest(raw=raw):
                self.assert_rejected_before_side_effects(raw)

    def test_unicode_digits_and_unbounded_digits_rejected(self):
        self.assert_rejected_before_side_effects("\u0667\u0662")
        self.assert_rejected_before_side_effects("9" * 100)

    def test_duplicate_host_and_origin_rejected_without_side_effects(self):
        # Email Message models duplicate HTTP headers; no socket is opened.
        for header, duplicate in (("Host", "localhost:8766"),
                                  ("Origin", "http://localhost:8766")):
            with self.subTest(header=header):
                handler, replies, length = self.handler_with_lengths()
                handler.headers.add_header("Content-Length", str(length))
                if header == "Origin":
                    handler.headers.add_header("Origin", "http://127.0.0.1:8766")
                handler.headers.add_header(header, duplicate)
                with mock.patch.object(setup, "save_preferences") as save, \
                     mock.patch.object(setup.subprocess, "Popen") as spawn:
                    handler.do_POST()
                self.assertEqual(replies[0][0], 403)
                save.assert_not_called()
                spawn.assert_not_called()

    def test_missing_length_rejected(self):
        self.assert_rejected_before_side_effects()

    def test_valid_ascii_decimal_reaches_runtime_preflight(self):
        _, _, length = self.handler_with_lengths()
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(setup, "RUNTIME", Path(temp) / "missing.py"), \
                 mock.patch.object(setup, "save_preferences") as save, \
                 mock.patch.object(setup.subprocess, "Popen") as spawn:
                for raw in (str(length), "0" + str(length)):
                    handler, replies, _ = self.handler_with_lengths(raw)
                    handler.do_POST()
                    self.assertEqual(replies[0][0], 503)
                    self.assertIn("runtime script is missing", replies[0][1]["error"])
                save.assert_not_called()
                spawn.assert_not_called()


    def test_short_body_rejected_even_when_received_json_is_valid(self):
        _, _, actual_length = self.handler_with_lengths()
        handler, replies, _ = self.handler_with_lengths(str(actual_length + 8))
        with mock.patch.object(setup, "save_preferences") as save, \
             mock.patch.object(setup.subprocess, "Popen") as spawn:
            handler.do_POST()
        self.assertEqual(replies, [(400, {"error": "incomplete request body"})])
        save.assert_not_called()
        spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
