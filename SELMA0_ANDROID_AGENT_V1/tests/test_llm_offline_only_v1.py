import os
import unittest
from unittest.mock import patch

from selma0_llm_router_android_v1 import Selma0LLMRouterAndroidV1


class OfflineOnlyRouterTests(unittest.TestCase):
    def test_offline_only_blocks_configured_cloud_fallback(self):
        env = {
            "SELMA0_LOCAL_BASE_URL_V1": "http://127.0.0.1:8080/v1",
            "SELMA0_LOCAL_MODEL_V1": "local",
            "SELMA0_ONLINE_BASE_URL_V1": "https://example.invalid/v1",
            "SELMA0_ONLINE_MODEL_V1": "remote",
            "SELMA0_ONLINE_API_KEY_V1": "secret",
            "SELMA0_OFFLINE_ONLY_V1": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            router = Selma0LLMRouterAndroidV1()

        calls = []
        def fake_chat(base, model, messages, api_key=""):
            calls.append(base)
            if base.startswith("http://127.0.0.1"):
                raise OSError("local unavailable")
            return "cloud response"

        router._chat = fake_chat
        result = router.reply([{"role": "user", "content": "hello"}])
        self.assertEqual("unavailable", result["route"])
        self.assertIn("offline-only", result["text"])
        self.assertEqual(["http://127.0.0.1:8080/v1"], calls)

    def test_explicit_online_mode_can_use_configured_fallback(self):
        env = {
            "SELMA0_LOCAL_BASE_URL_V1": "http://127.0.0.1:8080/v1",
            "SELMA0_LOCAL_MODEL_V1": "local",
            "SELMA0_ONLINE_BASE_URL_V1": "https://example.invalid/v1",
            "SELMA0_ONLINE_MODEL_V1": "remote",
            "SELMA0_ONLINE_API_KEY_V1": "secret",
            "SELMA0_OFFLINE_ONLY_V1": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            router = Selma0LLMRouterAndroidV1()

        calls = []
        def fake_chat(base, model, messages, api_key=""):
            calls.append(base)
            if base.startswith("http://127.0.0.1"):
                raise OSError("local unavailable")
            return "cloud response"

        router._chat = fake_chat
        result = router.reply([{"role": "user", "content": "hello"}])
        self.assertEqual("online-fallback", result["route"])
        self.assertEqual("cloud response", result["text"])
        self.assertEqual(
            ["http://127.0.0.1:8080/v1", "https://example.invalid/v1"],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
