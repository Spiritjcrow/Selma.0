#!/usr/bin/env python3
"""Unit tests for the optional on-device acceptance script, with no network I/O."""
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import selma0_offline_acceptance_android_v1 as acceptance


class OfflineAcceptanceTests(unittest.TestCase):
    READY = {
        "offline_only_supported": True,
        "local_llm_loopback": True,
        "local_llm": "http://127.0.0.1:8080/v1",
        "online_fallback_configured": True,
    }

    def test_status_only_never_sends_chat(self):
        with patch.object(acceptance, "local_request", return_value=dict(self.READY)) as send:
            with redirect_stdout(StringIO()):
                acceptance.verify(chat=False)
        send.assert_called_once_with("GET", "/api/selma0/status/v1")

    def test_chat_enforces_offline_only_flag_even_with_cloud_configured(self):
        messages = []
        def reply(method, path, payload=None):
            messages.append((method, path, payload))
            if method == "GET":
                return dict(self.READY)
            return {"ok": True, "result": {"route": "offline-local", "text": "Hi"}}
        with patch.object(acceptance, "local_request", side_effect=reply):
            with redirect_stdout(StringIO()):
                acceptance.verify(chat=True)
        self.assertEqual(len(messages), 2)
        method, path, payload = messages[1]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/api/selma0/chat/v1")
        self.assertIs(payload["offline_only"], True)
        self.assertIs(payload["confirmed"], True)
        self.assertTrue(payload["request_id"])

    def test_old_backend_is_refused(self):
        with patch.object(acceptance, "local_request", return_value={
            "local_llm_loopback": True,
        }) as send:
            with self.assertRaisesRegex(RuntimeError, "update"):
                acceptance.verify(chat=True)
        send.assert_called_once()

    def test_nonloopback_model_is_refused(self):
        status = dict(self.READY, local_llm_loopback=False)
        with patch.object(acceptance, "local_request", return_value=status) as send:
            with self.assertRaisesRegex(RuntimeError, "loopback"):
                acceptance.verify(chat=True)
        send.assert_called_once()

    def test_no_model_output_is_failure_not_success(self):
        with patch.object(acceptance, "local_request", side_effect=[
            dict(self.READY),
            {"ok": True, "result": {"route": "unavailable", "text": "Not running"}},
        ]):
            with redirect_stdout(StringIO()):
                with self.assertRaisesRegex(RuntimeError, "model route"):
                    acceptance.verify(chat=True)


if __name__ == "__main__":
    unittest.main()
