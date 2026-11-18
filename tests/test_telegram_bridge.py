"""Offline authorization checks for the optional Telegram bridge."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from adapters import telegram_bridge as tg


class TelegramBridgePolicyTests(unittest.TestCase):
    def test_status_never_claims_live_authorization(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {
            "SELMA_TG_SESSION_DIR": tmp,
            "SELMA_TG_API_ID": "1111",
            "SELMA_TG_API_HASH": "a" * 32,
            "SELMA_TG_SEND_ENABLED": "0",
        }):
            self.assertEqual(tg.status()["telegram_authorization_verified"], False)
            self.assertEqual(tg.status()["live_chatgpt_connector"], False)
            self.assertEqual(tg.status()["send_enabled"], False)
            self.assertFalse(tg.status()["local_session_present"])

    def test_send_denies_without_opt_in(self):
        with patch.dict("os.environ", {"SELMA_TG_SEND_ENABLED": "0", "SELMA_TG_SEND_ALLOWLIST": "me"}):
            with self.assertRaises(tg.TelegramBridgeError):
                tg.ensure_send_allowed("me", "hello", confirmed=True)

    def test_send_denies_unlisted_destination(self):
        with patch.dict("os.environ", {"SELMA_TG_SEND_ENABLED": "1", "SELMA_TG_SEND_ALLOWLIST": "me"}):
            with self.assertRaises(tg.TelegramBridgeError):
                tg.ensure_send_allowed("@otheruser", "hello", confirmed=True)

    def test_send_denies_without_per_message_confirmation(self):
        with patch.dict("os.environ", {"SELMA_TG_SEND_ENABLED": "1", "SELMA_TG_SEND_ALLOWLIST": "me"}):
            with self.assertRaises(tg.TelegramBridgeError):
                tg.ensure_send_allowed("me", "hello", confirmed=False)

    def test_send_denies_invalid_text(self):
        with patch.dict("os.environ", {"SELMA_TG_SEND_ENABLED": "1", "SELMA_TG_SEND_ALLOWLIST": "me"}):
            for text in ("", " ", "x" * 2001):
                with self.subTest(text_length=len(text)):
                    with self.assertRaises(tg.TelegramBridgeError):
                        tg.ensure_send_allowed("me", text, confirmed=True)

    def test_explicit_one_message_send_can_pass_policy(self):
        with patch.dict("os.environ", {"SELMA_TG_SEND_ENABLED": "yes", "SELMA_TG_SEND_ALLOWLIST": "me,@friend"}):
            tg.ensure_send_allowed("@friend", "Hello", confirmed=True)

    def test_status_runs_without_telegram_or_network(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"SELMA_TG_SESSION_DIR": tmp}):
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(tg.main(["status"]), 0)
            self.assertIn("telegram_authorization_verified", json.loads(out.getvalue()))
            self.assertNotIn("api_hash", out.getvalue())

    def test_no_send_connection_when_local_policy_fails(self):
        with patch.dict("os.environ", {"SELMA_TG_SEND_ENABLED": "0", "SELMA_TG_SEND_ALLOWLIST": "me"}):
            with patch.object(tg, "_authorized_client", side_effect=AssertionError("network used")):
                with redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(tg.main(["send", "--peer", "me", "--text", "hi", "--confirm-send"]), 2)
                self.assertIn("disabled", err.getvalue())

    def test_missing_session_denied_before_telegram_client(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"SELMA_TG_SESSION_DIR": tmp}):
            with self.assertRaises(tg.TelegramBridgeError):
                tg._authorized_client()

    def test_credentials_validation(self):
        with patch.dict("os.environ", {"SELMA_TG_API_ID": "1", "SELMA_TG_API_HASH": "not-a-hash"}):
            with self.assertRaises(tg.TelegramBridgeError):
                tg._credentials()


if __name__ == "__main__":
    unittest.main()
