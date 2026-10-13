"""Offline contract tests for the read-only Selma Telegram MCP interface."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from adapters import telegram_mcp as mod


class StubMCP:
    def __init__(self, name):
        self.name = name
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register


class TelegramMCPTests(unittest.TestCase):
    def test_registration_exposes_only_four_read_only_tools(self):
        server = mod.create_server(StubMCP)
        self.assertEqual(
            set(server.tools),
            {"telegram_status", "telegram_account", "telegram_list_dialogs", "telegram_list_messages"},
        )
        self.assertNotIn("telegram_send_message", server.tools)

    def test_status_is_offline_and_truthful(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {
            "SELMA_TG_SESSION_DIR": tmp,
            "SELMA_TG_MCP_READ_ENABLED": "0",
        }, clear=True):
            with patch.object(mod, "_invoke_cli", side_effect=AssertionError("CLI must not run")):
                result = mod.telegram_status()
            self.assertEqual(result["mcp_transport"], "stdio")
            self.assertFalse(result["mcp_read_enabled"])
            self.assertFalse(result["telegram_authorization_verified"])
            self.assertFalse(result["live_chatgpt_connector"])
            self.assertFalse(result["mcp_write_available"])

    def test_account_denied_without_local_opt_in(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(mod, "_invoke_cli", side_effect=AssertionError("must not run")):
                result = mod.telegram_account()
        self.assertFalse(result["ok"])
        self.assertIn("disabled", result["error"])

    def test_dialogs_denied_without_local_opt_in(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(mod, "_invoke_cli", side_effect=AssertionError("must not run")):
                result = mod.telegram_list_dialogs()
        self.assertFalse(result["ok"])

    def test_message_body_needs_separate_flag(self):
        with patch.dict("os.environ", {
            "SELMA_TG_MCP_READ_ENABLED": "1", "SELMA_TG_MCP_READ_TEXT_ENABLED": "0",
        }, clear=True):
            with patch.object(mod, "_invoke_cli", side_effect=AssertionError("must not run")):
                result = mod.telegram_list_messages("me", include_text=True)
        self.assertFalse(result["ok"])
        self.assertIn("Message-body", result["error"])

    def test_allowlisted_metadata_read_generates_bounded_cli_call(self):
        with patch.dict("os.environ", {"SELMA_TG_MCP_READ_ENABLED": "1"}, clear=True):
            with patch.object(mod, "_invoke_cli", return_value={"ok": True, "messages": []}) as invoke:
                result = mod.telegram_list_messages("me", limit=3)
                self.assertTrue(result["ok"])
                invoke.assert_called_once_with("messages", "--peer", "me", "--limit", "3")

    def test_enabled_message_text_forwarded_only_when_opted_in(self):
        with patch.dict("os.environ", {
            "SELMA_TG_MCP_READ_ENABLED": "1", "SELMA_TG_MCP_READ_TEXT_ENABLED": "1",
        }, clear=True):
            with patch.object(mod, "_invoke_cli", return_value={"ok": True}) as invoke:
                mod.telegram_list_messages("me", include_text=True)
                self.assertEqual(invoke.call_args.args[-1], "--show-text")

    def test_default_allowlist_blocks_other_chat(self):
        with patch.dict("os.environ", {"SELMA_TG_MCP_READ_ENABLED": "1"}, clear=True):
            with patch.object(mod, "_invoke_cli", side_effect=AssertionError("must not run")):
                result = mod.telegram_list_messages("@someone", limit=3)
        self.assertFalse(result["ok"])
        self.assertIn("allowlist", result["error"])

    def test_numeric_chat_can_be_locally_allowlisted(self):
        with patch.dict("os.environ", {
            "SELMA_TG_MCP_READ_ENABLED": "1",
            "SELMA_TG_MCP_READ_ALLOWLIST": "-1001234567",
        }, clear=True):
            with patch.object(mod, "_invoke_cli", return_value={"ok": True}) as invoke:
                result = mod.telegram_list_messages("-1001234567", limit=1)
        self.assertTrue(result["ok"])
        invoke.assert_called_once()

    def test_invalid_limits_are_rejected_before_cli(self):
        with patch.dict("os.environ", {"SELMA_TG_MCP_READ_ENABLED": "1"}, clear=True):
            with patch.object(mod, "_invoke_cli", side_effect=AssertionError("must not run")):
                for limit in (0, 21, -1, True, "5"):
                    with self.subTest(limit=limit):
                        self.assertFalse(mod.telegram_list_dialogs(limit)["ok"])

    def test_bad_peer_rejected_before_cli(self):
        with patch.dict("os.environ", {"SELMA_TG_MCP_READ_ENABLED": "1"}, clear=True):
            with patch.object(mod, "_invoke_cli", side_effect=AssertionError("must not run")):
                for peer in ("--send", "me\nsecret", "", "@bad peer", "https://example.com"):
                    with self.subTest(peer=peer):
                        self.assertFalse(mod.telegram_list_messages(peer)["ok"])

    def test_cli_refuses_unsupported_operation(self):
        with patch.object(mod.subprocess, "run", side_effect=AssertionError("must not spawn")):
            self.assertFalse(mod._invoke_cli("send", "--peer", "me")["ok"])
            self.assertFalse(mod._invoke_cli("login")["ok"])

    def test_cli_never_logs_child_stderr(self):
        with patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
            returncode=2, stdout="", stderr="SECRET SESSION AUTH CODE"
        )) as run:
            result = mod._invoke_cli("account")
        self.assertFalse(result["ok"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["check"], False)
        self.assertIsInstance(run.call_args.kwargs["timeout"], int)

    def test_cli_handles_timeout_and_invalid_output(self):
        with patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired(["python"], 35)):
            self.assertFalse(mod._invoke_cli("account")["ok"])
        with patch.object(mod.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout="nope", stderr=""
        )):
            self.assertFalse(mod._invoke_cli("account")["ok"])

    def test_read_metadata_does_not_reveal_credentials(self):
        with patch.dict("os.environ", {
            "SELMA_TG_API_ID": "1234", "SELMA_TG_API_HASH": "a" * 32,
            "SELMA_TG_MCP_READ_ENABLED": "1",
        }, clear=True):
            status = json.dumps(mod.telegram_status())
        self.assertNotIn("1234", status)
        self.assertNotIn("a" * 32, status)


if __name__ == "__main__":
    unittest.main()
