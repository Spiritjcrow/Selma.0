#!/usr/bin/env python3
import json
import os
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_llm_router_android_v1 import Selma0LLMRouterAndroidV1


class _Response:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class LLMRouterContractTests(unittest.TestCase):
    def _router(self, env=None):
        base = {
            "SELMA0_LOCAL_BASE_URL_V1": "http://127.0.0.1:8080/v1",
            "SELMA0_LOCAL_MODEL_V1": "selma0-local",
            "SELMA0_LLM_TIMEOUT_V1": "1",
        }
        base.update(env or {})
        with patch.dict(os.environ, base, clear=True):
            return Selma0LLMRouterAndroidV1()

    def test_local_success_never_contacts_fallback(self):
        router = self._router({
            "SELMA0_ONLINE_BASE_URL_V1": "https://fallback.invalid/v1",
            "SELMA0_ONLINE_MODEL_V1": "fallback",
        })
        calls = []

        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            return _Response({"choices": [{"message": {"content": "local answer"}}]})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = router.reply([{"role": "user", "content": "ping"}])

        self.assertEqual(result["route"], "offline-local")
        self.assertEqual(result["text"], "local answer")
        self.assertEqual(calls, ["http://127.0.0.1:8080/v1/chat/completions"])

    def test_local_failure_without_fallback_fails_closed(self):
        router = self._router()
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            result = router.reply([{"role": "user", "content": "ping"}])

        self.assertEqual(result["route"], "unavailable")
        self.assertIn("timed out", result["error"])

    def test_malformed_local_response_is_unavailable_without_fallback(self):
        router = self._router()
        with patch("urllib.request.urlopen", return_value=_Response({"choices": []})):
            result = router.reply([{"role": "user", "content": "ping"}])

        self.assertEqual(result["route"], "unavailable")
        self.assertTrue(result["error"])

    def test_explicit_fallback_is_used_only_after_local_failure(self):
        router = self._router({
            "SELMA0_ONLINE_BASE_URL_V1": "https://fallback.invalid/v1",
            "SELMA0_ONLINE_MODEL_V1": "fallback",
            "SELMA0_ONLINE_API_KEY_V1": "test-key",
        })
        calls = []

        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            if req.full_url.startswith("http://127.0.0.1"):
                raise TimeoutError("local down")
            self.assertEqual(req.get_header("Authorization"), "Bearer test-key")
            return _Response({"choices": [{"message": {"content": "fallback answer"}}]})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = router.reply([{"role": "user", "content": "ping"}])

        self.assertEqual(result["route"], "online-fallback")
        self.assertEqual(result["text"], "fallback answer")
        self.assertEqual(calls, [
            "http://127.0.0.1:8080/v1/chat/completions",
            "https://fallback.invalid/v1/chat/completions",
        ])


if __name__ == "__main__":
    unittest.main()
