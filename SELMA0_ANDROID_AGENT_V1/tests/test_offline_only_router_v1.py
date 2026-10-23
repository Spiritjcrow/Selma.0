#!/usr/bin/env python3
"""Network-free regression tests for strict offline model routing."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selma0_llm_router_android_v1 import Selma0LLMRouterAndroidV1, _DenyRedirect


class OfflineOnlyRouterTests(unittest.TestCase):
    def router(self, **overrides):
        env = {
            "SELMA0_LOCAL_BASE_URL_V1": "http://127.0.0.1:8080/v1",
            "SELMA0_ONLINE_BASE_URL_V1": "https://example.invalid/v1",
            "SELMA0_ONLINE_MODEL_V1": "cloud",
            "SELMA0_ONLINE_API_KEY_V1": "test-only",
        }
        env.update(overrides)
        with patch.dict(os.environ, env):
            return Selma0LLMRouterAndroidV1()

    def test_strict_offline_accepts_loopback_only(self):
        router = self.router()
        for url in ("http://127.0.0.1:8080/v1", "http://localhost:8080/v1", "http://[::1]:8080/v1"):
            with self.subTest(url=url):
                router.local_base = url
                self.assertTrue(router.is_loopback_local())
        for url in (
            "https://external.example/v1", "http://localhost.evil.invalid/v1",
            "http://127.0.0.1.evil.invalid/v1", "http://user@127.0.0.1:8080/v1",
            "ftp://127.0.0.1/v1", "http://127.0.0.1:99999/v1",
        ):
            with self.subTest(url=url):
                router.local_base = url
                self.assertFalse(router.is_loopback_local())

    def test_strict_offline_refuses_remote_base_before_network(self):
        router = self.router(SELMA0_LOCAL_BASE_URL_V1="https://external.example/v1")
        with patch.object(router, "_chat") as chat:
            reply = router.reply([{"role": "user", "content": "hello"}], offline_only=True)
        chat.assert_not_called()
        self.assertEqual(reply["route"], "unavailable")

    def test_strict_offline_does_not_call_cloud_when_local_fails(self):
        router = self.router()
        with patch.object(router, "_chat", side_effect=ConnectionError("local model stopped")) as chat:
            reply = router.reply([], offline_only=True)
        self.assertEqual(reply["route"], "unavailable")
        self.assertEqual(chat.call_count, 1)
        self.assertTrue(chat.call_args.kwargs["local_only"])

    def test_strict_offline_replies_from_local_model(self):
        router = self.router()
        with patch.object(router, "_chat", return_value="verified local response") as chat:
            reply = router.reply([], offline_only=True)
        self.assertEqual(reply["text"], "verified local response")
        self.assertEqual(reply["route"], "offline-local")
        self.assertEqual(chat.call_count, 1)

    def test_legacy_online_fallback_requires_non_strict_call(self):
        router = self.router()
        with patch.object(router, "_chat", side_effect=[ConnectionError("stopped"), "cloud response"]) as chat:
            reply = router.reply([], offline_only=False)
        self.assertEqual(reply["route"], "online-fallback")
        self.assertEqual(chat.call_count, 2)

    def test_redirect_handler_rejects_redirects(self):
        handler = _DenyRedirect()
        self.assertIsNone(handler.redirect_request(
            Mock(), None, 307, "redirect", {}, "https://external.example/"
        ))

    def test_strict_transport_ignores_proxy_env(self):
        router = self.router()
        response = MagicMock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"choices":[{"message":{"content":"hello"}}]}'
        opener = Mock()
        opener.open.return_value = response
        with patch("urllib.request.build_opener", return_value=opener) as build:
            reply = router.reply([], offline_only=True)
        self.assertEqual(reply["route"], "offline-local")
        handlers = build.call_args.args
        self.assertTrue(any(getattr(h, "proxies", None) == {} for h in handlers))
        self.assertTrue(any(isinstance(h, _DenyRedirect) for h in handlers))


if __name__ == "__main__":
    unittest.main()
