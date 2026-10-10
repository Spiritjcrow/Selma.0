import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selma0_gemini_adapter_v1 import handoff_gemini, request_gemini


class FakeHTTP:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def read(self, _):
        return self.payload


class GeminiAdapterTests(unittest.TestCase):
    def env(self, **updates):
        base = {"SELMA0_GEMINI_API_ENABLED_V1": "1",
                "GEMINI_API_KEY": "test_key_for_mock_only_123",
                "SELMA0_BRIDGE_HMAC_KEY_V1": "ab" * 32}
        base.update(updates)
        return patch.dict(os.environ, base)

    def test_1_default_disallows_network_even_if_key_exists(self):
        with self.env(SELMA0_GEMINI_API_ENABLED_V1=""):
            with self.assertRaises(PermissionError):
                request_gemini("Proposal", authorize_external=True,
                               opener=lambda *_args, **_kw: self.fail("network used"))

    def test_2_per_invocation_approval_required(self):
        with self.env():
            with self.assertRaises(PermissionError):
                request_gemini("Proposal", authorize_external=False,
                               opener=lambda *_args, **_kw: self.fail("network used"))

    def test_3_outbound_secret_guard(self):
        with self.env():
            with self.assertRaises(ValueError):
                request_gemini("api_key=supersecretcredential", authorize_external=True,
                               opener=lambda *_args, **_kw: self.fail("network used"))

    def test_4_model_cannot_redirect_to_another_host(self):
        with self.env(SELMA0_GEMINI_MODEL_V1="../../evil"):
            with self.assertRaises(ValueError):
                request_gemini("Proposal", authorize_external=True,
                               opener=lambda *_args, **_kw: self.fail("network used"))

    def test_5_explicit_mocked_api_response_is_signed_locally(self):
        seen = []
        def opener(req, timeout):
            seen.append((req.full_url, timeout, dict(req.header_items())))
            return FakeHTTP({"candidates": [{"content": {"parts": [
                {"text": "Add a schema validator; verify with tests."}]}}]})
        forwarded = []
        def relay(message, speaker):
            forwarded.append((message, speaker))
            return {"ok": True}
        with self.env():
            output = handoff_gemini("How should the bridge be tested?", authorize_external=True,
                                    opener=opener, relay=relay)
        self.assertTrue(seen[0][0].startswith("https://generativelanguage.googleapis.com/v1beta/models/"))
        self.assertTrue(any(k.lower() == "x-goog-api-key" for k in seen[0][2]))
        self.assertEqual(forwarded[0][1], "gemini")
        self.assertEqual(output["local_handoff"], {"ok": True})

    def test_6_missing_local_key_fails_before_paid_provider_request(self):
        with self.env(SELMA0_BRIDGE_HMAC_KEY_V1=""):
            with self.assertRaises(ValueError):
                handoff_gemini("Proposal", authorize_external=True,
                               opener=lambda *_a, **_kw: self.fail("provider called"))

    def test_7_api_response_missing_text_rejected(self):
        with self.env():
            with self.assertRaises(ValueError):
                request_gemini("Proposal", authorize_external=True,
                               opener=lambda *_a, **_kw: FakeHTTP({"candidates": []}))


if __name__ == "__main__":
    unittest.main()
