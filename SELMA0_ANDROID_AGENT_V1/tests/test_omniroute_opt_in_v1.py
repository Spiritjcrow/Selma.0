"""Offline-first behavior is preserved when OmniRoute is added as an opt-in endpoint."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selma0_llm_router_android_v1 import Selma0LLMRouterAndroidV1


class OmniRouteOptInTests(unittest.TestCase):
    def test_default_is_offline_only(self):
        with patch.dict(os.environ, {}, clear=True):
            router = Selma0LLMRouterAndroidV1()
        self.assertEqual(router.online_base, "")
        with patch.object(router, "_chat", side_effect=ConnectionError("not running")) as chat:
            result = router.reply([{"role": "user", "content": "ping"}])
        self.assertEqual(result["route"], "unavailable")
        self.assertEqual(chat.call_count, 1)

    def test_local_succeeds_without_sending_to_gateway(self):
        config = {
            "SELMA0_ONLINE_BASE_URL_V1": "http://127.0.0.1:20128/v1",
            "SELMA0_ONLINE_MODEL_V1": "auto/subscription",
            "SELMA0_ONLINE_API_KEY_V1": "test-only-key",
        }
        with patch.dict(os.environ, config, clear=True):
            router = Selma0LLMRouterAndroidV1()
        with patch.object(router, "_chat", return_value="offline reply") as chat:
            result = router.reply([{"role": "user", "content": "ping"}])
        self.assertEqual(result["route"], "offline-local")
        chat.assert_called_once()
        self.assertEqual(chat.call_args.args[0], "http://127.0.0.1:8080/v1")

    def test_gateway_used_only_after_local_failure_and_explicit_config(self):
        config = {
            "SELMA0_ONLINE_BASE_URL_V1": "http://127.0.0.1:20128/v1",
            "SELMA0_ONLINE_MODEL_V1": "auto/subscription",
            "SELMA0_ONLINE_API_KEY_V1": "test-only-key",
        }
        with patch.dict(os.environ, config, clear=True):
            router = Selma0LLMRouterAndroidV1()
        with patch.object(router, "_chat", side_effect=[ConnectionError("offline"), "gateway reply"]) as chat:
            result = router.reply([{"role": "user", "content": "ping"}])
        self.assertEqual(result["route"], "online-fallback")
        self.assertEqual(chat.call_count, 2)
        self.assertEqual(chat.call_args.args[0], "http://127.0.0.1:20128/v1")
        self.assertEqual(chat.call_args.args[1], "auto/subscription")
        self.assertEqual(chat.call_args.args[3], "test-only-key")


if __name__ == "__main__":
    unittest.main()
