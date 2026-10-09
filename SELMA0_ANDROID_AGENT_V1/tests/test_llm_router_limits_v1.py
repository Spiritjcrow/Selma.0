import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selma0_llm_router_android_v1 import (
    Selma0LLMRouterAndroidV1,
    Selma0OversizedResponseError,
)


class CapturedResponse:
    def __init__(self, data):
        self.buffer = io.BytesIO(data)
        self.read_limits = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        self.read_limits.append(size)
        return self.buffer.read(size)


class TestLLMRouterResponseLimits(unittest.TestCase):
    def setUp(self):
        self.router = Selma0LLMRouterAndroidV1()
        self.router.online_base = "https://unit-test.invalid/v1"
        self.router.online_model = "test-model"
        self.router.online_key = "dummy-only"

    def test_normal_response_parses(self):
        response = CapturedResponse(json.dumps({
            "choices": [{"message": {"content": "ok"}}]
        }).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=response):
            self.assertEqual(self.router._chat("http://127.0.0.1:8080/v1", "m", []), "ok")
        self.assertEqual(response.read_limits, [self.router.MAX_RESPONSE_BYTES + 1])

    def test_oversized_response_rejected(self):
        response = CapturedResponse(b"a" * (self.router.MAX_RESPONSE_BYTES + 1))
        with patch("urllib.request.urlopen", return_value=response):
            with self.assertRaises(Selma0OversizedResponseError):
                self.router._chat("http://127.0.0.1:8080/v1", "m", [])
        self.assertEqual(response.read_limits, [self.router.MAX_RESPONSE_BYTES + 1])

    def test_oversize_cannot_trigger_cloud_fallback(self):
        first = CapturedResponse(b"a" * (self.router.MAX_RESPONSE_BYTES + 1))
        with patch("urllib.request.urlopen", return_value=first) as urlopen:
            result = self.router.reply([{"role": "user", "content": "private dummy text"}])
        self.assertEqual(result["route"], "unavailable")
        self.assertEqual(result["error"], "local_response_size_limit")
        self.assertEqual(urlopen.call_count, 1)

    def test_normal_local_failure_still_uses_configured_fallback(self):
        fallback = CapturedResponse(b'{"choices":[{"message":{"content":"fallback"}}]}')
        with patch("urllib.request.urlopen", side_effect=[OSError("offline"), fallback]) as urlopen:
            result = self.router.reply([{"role": "user", "content": "dummy"}])
        self.assertEqual(result["route"], "online-fallback")
        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
