"""Offline-only provider contract tests. No API keys or external network required."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selma0_provider_layers_v1 import PROVIDERS, request, main


class FakeResponse:
    def __init__(self, obj):
        self.body = json.dumps(obj).encode()
    def read(self, max_size):
        return self.body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class AdapterTests(unittest.TestCase):
    message = [{"role": "user", "content": "hello"}]

    def test_no_network_default(self):
        called = []
        result = request("claude", self.message, transport=lambda *a, **k: called.append(True))
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(called)

    def test_all_providers_present(self):
        self.assertEqual(set(PROVIDERS), {"claude", "grok", "gemini", "kimi", "deepseek"})

    def test_missing_key_fails_closed(self):
        result = request("claude", self.message, allow_network=True, approved_paid=True, environ={})
        self.assertEqual(result["status"], "unavailable")

    def test_missing_model_fails_closed(self):
        result = request("kimi", self.message, allow_network=True, approved_paid=True, environ={"KIMI_API_KEY": "private"})
        self.assertEqual(result["status"], "unavailable")

    def test_no_automatic_other_provider_fallback(self):
        called = []
        def failed(req, **kwargs):
            called.append(req.full_url)
            raise OSError("secret diagnostic")
        result = request("claude", self.message, allow_network=True, approved_paid=True, environ={"ANTHROPIC_API_KEY": "private"}, transport=failed)
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(called), 1)
        self.assertNotIn("private", str(result))
        self.assertNotIn("secret", str(result))

    def test_claude_payload(self):
        def fake(req, **kwargs):
            self.assertEqual(req.full_url, "https://api.anthropic.com/v1/messages")
            data = json.loads(req.data)
            self.assertEqual(data["model"], "claude-fable-5-2")
            self.assertNotIn("temperature", data)
            self.assertEqual(data["messages"], self.message)
            self.assertEqual(req.get_header("Anthropic-version"), "2026-10-21")
            return FakeResponse({"content": [{"type": "text", "text": "Claude reply"}]})
        result = request("claude", self.message, allow_network=True, approved_paid=True, environ={"ANTHROPIC_API_KEY": "private"}, transport=fake)
        self.assertEqual(result["text"], "Claude reply")

    def test_grok_response_payload(self):
        def fake(req, **kwargs):
            self.assertTrue(req.full_url.endswith("/responses"))
            self.assertIn("input", json.loads(req.data))
            return FakeResponse({"output": [{"type": "message", "content": [{"type": "output_text", "text": "Grok reply"}]}]})
        result = request("grok", self.message, allow_network=True, approved_paid=True, environ={"XAI_API_KEY": "private"}, transport=fake)
        self.assertEqual(result["text"], "Grok reply")

    def test_gemini_format(self):
        def fake(req, **kwargs):
            self.assertIn("gemini-3.8-flash:generateContent", req.full_url)
            self.assertEqual(json.loads(req.data)["contents"][0]["role"], "user")
            return FakeResponse({"candidates": [{"content": {"parts": [{"text": "Gemini reply"}]}}]})
        result = request("gemini", self.message, allow_network=True, approved_paid=True, model="gemini-3.8-flash", environ={"GEMINI_API_KEY": "private"}, transport=fake)
        self.assertEqual(result["text"], "Gemini reply")

    def test_kimi_and_deepseek_chat(self):
        for provider, key, model in (("kimi", "KIMI_API_KEY", "kimi-k2"), ("deepseek", "DEEPSEEK_API_KEY", "deepseek-flash")):
            with self.subTest(provider=provider):
                def fake(req, **kwargs):
                    self.assertEqual(json.loads(req.data)["messages"], self.message)
                    return FakeResponse({"choices": [{"message": {"content": "text"}}]})
                result = request(provider, self.message, allow_network=True, approved_paid=True, model=model, environ={key: "private"}, transport=fake)
                self.assertEqual(result["text"], "text")

    def test_reject_role_injection(self):
        result = request("claude", [{"role": "tool", "content": "unsafe"}], allow_network=True, approved_paid=True, environ={"ANTHROPIC_API_KEY": "private"})
        self.assertEqual(result["status"], "error")

    def test_reject_model_path(self):
        result = request("gemini", self.message, allow_network=True, approved_paid=True, model="../../other", environ={"GEMINI_API_KEY": "private"})
        self.assertEqual(result["status"], "unavailable")


    def test_local_mock_default_has_zero_network_and_no_bill(self):
        calls = []
        result = request("mock", self.message, transport=lambda *a, **k: calls.append(True), environ={})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["provider"], "mock")
        self.assertIs(result["network"], False)
        self.assertIs(result["billable"], False)
        self.assertEqual(calls, [])
        self.assertNotIn("hello", result["text"])

    def test_local_mock_ignores_remote_network_flags(self):
        calls = []
        result = request("mock", self.message, allow_network=True, approved_paid=True,
                         transport=lambda *a, **k: calls.append(True),
                         environ={"ANTHROPIC_API_KEY": "private"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(calls, [])

    def test_paid_consent_is_required_even_with_network_allowed(self):
        calls = []
        result = request("claude", self.message, allow_network=True,
                         transport=lambda *a, **k: calls.append(True),
                         environ={"ANTHROPIC_API_KEY": "private"})
        self.assertEqual(result["status"], "blocked")
        self.assertIn("paid-provider approval", result["reason"])
        self.assertFalse(calls)

    def test_paid_consent_cannot_bypass_disabled_network(self):
        calls = []
        result = request("claude", self.message, approved_paid=True,
                         transport=lambda *a, **k: calls.append(True),
                         environ={"ANTHROPIC_API_KEY": "private"})
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(calls)

    def test_nonboolean_approval_flags_are_rejected(self):
        calls = []
        result = request("claude", self.message, allow_network="yes", approved_paid=True,
                         transport=lambda *a, **k: calls.append(True),
                         environ={"ANTHROPIC_API_KEY": "private"})
        self.assertEqual(result["status"], "blocked")
        result = request("claude", self.message, allow_network=True, approved_paid=1,
                         transport=lambda *a, **k: calls.append(True),
                         environ={"ANTHROPIC_API_KEY": "private"})
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(calls)

    def test_mock_rejects_bad_messages_and_token_budget(self):
        calls = []
        for messages, tokens in (([], 512), (self.message, 0), (self.message, True),
                                 ([{"role": "tool", "content": "bad"}], 512)):
            with self.subTest(messages=messages, tokens=tokens):
                result = request("mock", messages, max_tokens=tokens,
                                 transport=lambda *a, **k: calls.append(True))
                self.assertEqual(result["status"], "error")
        self.assertFalse(calls)

    def test_cli_defaults_to_no_cost_mock(self):
        import io
        from unittest.mock import patch
        output = io.StringIO()
        with patch.object(sys, "argv", ["provider", "--message", "hello"]), patch("sys.stdout", output):
            exit_code = main()
        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(result["provider"], "mock")
        self.assertIs(result["billable"], False)

    def test_cli_execute_alone_cannot_pay(self):
        import io
        from unittest.mock import patch
        output = io.StringIO()
        with patch.object(sys, "argv", ["provider", "--provider", "claude", "--message", "hi", "--execute"]), patch("sys.stdout", output):
            exit_code = main()
        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("paid-provider approval", result["reason"])


if __name__ == "__main__":
    unittest.main()
