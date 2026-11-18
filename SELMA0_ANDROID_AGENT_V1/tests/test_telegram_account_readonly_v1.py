"""Offline, no-credential contract tests for the Somagram read-only bridge."""
import asyncio
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "selma0_telegram_account_readonly_v1.py"
spec = importlib.util.spec_from_file_location("somagram_readonly_v1", SOURCE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class FakeTelegramClient:
    calls = []
    authorized = True
    def __init__(self, name, api_id, api_hash, *, receive_updates):
        assert not receive_updates
        self.calls.append(("init", api_id, str(name)))
        self.started = False
    async def start(self):
        self.calls.append(("start",))
        self.started = True
    async def connect(self):
        self.calls.append(("connect",))
    async def is_user_authorized(self):
        return type(self).authorized
    async def get_me(self):
        self.calls.append(("get_me",))
        return types.SimpleNamespace(username="selma_test", id=123)
    async def get_dialogs(self, *, limit):
        self.calls.append(("get_dialogs", limit))
        return [types.SimpleNamespace(title="Sample Conversation")]
    async def disconnect(self):
        self.calls.append(("disconnect",))


class SomagramReadOnlyTests(unittest.TestCase):
    def setUp(self):
        FakeTelegramClient.calls = []
        FakeTelegramClient.authorized = True

    def test_api_id_and_hash_validation(self):
        with patch.dict(os.environ, {
            "SELMA0_TELEGRAM_API_ID_V1": "12345",
            "SELMA0_TELEGRAM_API_HASH_V1": "example-not-real",
        }):
            self.assertEqual((12345, "example-not-real"), bridge.credentials())
        with patch.dict(os.environ, {
            "SELMA0_TELEGRAM_API_ID_V1": "not-a-number",
            "SELMA0_TELEGRAM_API_HASH_V1": "example-not-real",
        }):
            with self.assertRaises(ValueError):
                bridge.credentials()

    def test_session_is_outside_repository_and_mode_private(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            bridge.Path, "home", return_value=Path(tmp)
        ):
            base = bridge.session_base()
            self.assertTrue(str(base).startswith(str(Path(tmp))))
            self.assertEqual(0o700, base.parent.stat().st_mode & 0o777)
            self.assertEqual("somagram_user_v1", base.name)

    def test_world_readable_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            bridge.Path, "home", return_value=Path(tmp)
        ):
            base = bridge.session_base()
            file = base.with_suffix(".session")
            file.write_text("placeholder only", encoding="utf-8")
            file.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, "permissions too broad"):
                bridge.session_base()

    def execute(self, command):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "session"
            fake = types.SimpleNamespace(TelegramClient=FakeTelegramClient)
            with patch.dict(sys.modules, {"telethon": fake}), patch.object(
                bridge, "credentials", return_value=(12345, "fakehash")
            ), patch.object(bridge, "session_base", return_value=base):
                return asyncio.run(bridge.perform(command, 3))

    def test_login_only_authenticates_and_reads_identity(self):
        self.assertEqual(0, self.execute("login"))
        self.assertIn(("start",), FakeTelegramClient.calls)
        self.assertIn(("get_me",), FakeTelegramClient.calls)
        self.assertNotIn(("get_dialogs", 3), FakeTelegramClient.calls)

    def test_status_checks_existing_authorization_without_logging_in(self):
        self.assertEqual(0, self.execute("status"))
        self.assertIn(("connect",), FakeTelegramClient.calls)
        self.assertNotIn(("start",), FakeTelegramClient.calls)

    def test_dialogs_reads_titles_only(self):
        self.assertEqual(0, self.execute("dialogs"))
        self.assertIn(("get_dialogs", 3), FakeTelegramClient.calls)
        self.assertNotIn(("start",), FakeTelegramClient.calls)

    def test_unauthorized_session_rejected_without_login(self):
        FakeTelegramClient.authorized = False
        self.assertEqual(2, self.execute("dialogs"))
        self.assertNotIn(("get_me",), FakeTelegramClient.calls)

    def test_unsupported_action_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            asyncio.run(bridge.perform("send_message"))


if __name__ == "__main__":
    unittest.main()
