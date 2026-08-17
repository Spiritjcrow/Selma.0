#!/usr/bin/env python3
import io
import json
import os
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_github_adapter_android_v1 import (
    _GITHUB_API_VERSION_V1,
    _MAX_RESPONSE_BYTES_V1,
    _NoRedirectHandlerV1,
    Selma0GitHubAdapterAndroidV1,
)
from selma0_plugin_adapter_registry_android_v1 import (
    Selma0PluginAdapterRegistryAndroidV1,
    register_plugin_status_tool,
)
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1
from selma0_github_adapter_android_v1 import register_github_adapter_tools


class FakeResponse:
    def __init__(self, payload=None, raw=None):
        if raw is None:
            raw = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self._stream = io.BytesIO(raw)

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOpener:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class DummyAdapter:
    def __init__(self, status):
        self._status = status

    def status(self):
        return dict(self._status)


class PluginRegistryTests(unittest.TestCase):
    def test_registry_rejects_duplicate_adapter_names(self):
        registry = Selma0PluginAdapterRegistryAndroidV1()
        registry.register("github", DummyAdapter({"configured": True}))
        with self.assertRaises(ValueError):
            registry.register("github", DummyAdapter({"configured": False}))

    def test_plugin_status_tool_is_sensitive_read(self):
        plugins = Selma0PluginAdapterRegistryAndroidV1()
        tools = Selma0ToolRegistryAndroidV1()
        register_plugin_status_tool(tools, plugins)
        self.assertEqual(tools.describe("plugins.status")["risk"], "sensitive_read")


class GitHubAdapterTests(unittest.TestCase):
    def test_status_never_exposes_token_value(self):
        with patch.dict(
            os.environ,
            {"SELMA0_GITHUB_TOKEN_V1": "super-secret-token"},
            clear=True,
        ):
            adapter = Selma0GitHubAdapterAndroidV1(repo_spec="Spiritjcrow/Selma.0", opener=FakeOpener())
            status = adapter.status()
            serialized = json.dumps(status)
            self.assertTrue(status["write_configured"])
            self.assertTrue(status["credential_configured"])
            self.assertFalse(status["credential_exposed"])
            self.assertNotIn("super-secret-token", serialized)

    def test_invalid_repo_configuration_fails_before_network(self):
        opener = FakeOpener()
        adapter = Selma0GitHubAdapterAndroidV1(repo_spec="owner/repo?escape=1", opener=opener)
        with self.assertRaises(ValueError):
            adapter.repo_summary()
        self.assertEqual(opener.calls, [])

    def test_public_repo_summary_does_not_require_token(self):
        opener = FakeOpener(
            [
                FakeResponse(
                    {
                        "full_name": "Spiritjcrow/Selma.0",
                        "private": True,
                        "archived": False,
                        "disabled": False,
                        "default_branch": "main",
                        "open_issues_count": 7,
                        "updated_at": "2026-08-17T00:00:00Z",
                        "html_url": "https://github.com/Spiritjcrow/Selma.0",
                    }
                )
            ]
        )
        with patch.dict(os.environ, {}, clear=True):
            adapter = Selma0GitHubAdapterAndroidV1(repo_spec="Spiritjcrow/Selma.0", opener=opener)
            result = adapter.repo_summary()
        self.assertTrue(result["ok"])
        request, timeout = opener.calls[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(request.full_url, "https://api.github.com/repos/Spiritjcrow/Selma.0")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(headers["x-github-api-version"], _GITHUB_API_VERSION_V1)
        self.assertNotIn("authorization", headers)
        self.assertEqual(timeout, 15)

    def test_issue_listing_filters_pull_requests(self):
        opener = FakeOpener(
            [
                FakeResponse(
                    [
                        {
                            "number": 1,
                            "title": "Real issue",
                            "state": "open",
                            "labels": [{"name": "bug"}],
                            "updated_at": "2026-08-17T00:00:00Z",
                            "html_url": "https://github.com/example/repo/issues/1",
                        },
                        {
                            "number": 2,
                            "title": "PR disguised as issue",
                            "state": "open",
                            "labels": [],
                            "pull_request": {"url": "x"},
                        },
                    ]
                )
            ]
        )
        adapter = Selma0GitHubAdapterAndroidV1(repo_spec="example/repo", opener=opener)
        result = adapter.list_issues(state="open", limit=10)
        self.assertEqual(result["issue_count"], 1)
        self.assertEqual(result["issues"][0]["title"], "Real issue")
        self.assertEqual(result["issues"][0]["labels"], ["bug"])
        self.assertIn("per_page=10", opener.calls[0][0].full_url)

    def test_create_issue_requires_token_before_network(self):
        opener = FakeOpener()
        with patch.dict(os.environ, {}, clear=True):
            adapter = Selma0GitHubAdapterAndroidV1(repo_spec="example/repo", opener=opener)
            with self.assertRaises(RuntimeError):
                adapter.create_issue("Test")
        self.assertEqual(opener.calls, [])

    def test_create_issue_uses_bearer_header_and_bounded_payload(self):
        opener = FakeOpener(
            [
                FakeResponse(
                    {
                        "number": 12,
                        "title": "Test issue",
                        "state": "open",
                        "html_url": "https://github.com/example/repo/issues/12",
                        "created_at": "2026-08-17T00:00:00Z",
                    }
                )
            ]
        )
        with patch.dict(os.environ, {"SELMA0_GITHUB_TOKEN_V1": "token-value"}, clear=True):
            adapter = Selma0GitHubAdapterAndroidV1(repo_spec="example/repo", opener=opener)
            result = adapter.create_issue("Test issue", body="Body", labels=["selma"])
        self.assertEqual(result["number"], 12)
        request, _timeout = opener.calls[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(headers["authorization"], "Bearer token-value")
        self.assertEqual(headers["x-github-api-version"], _GITHUB_API_VERSION_V1)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {"title": "Test issue", "body": "Body", "labels": ["selma"]})
        self.assertNotIn("token-value", request.full_url)

    def test_large_response_is_rejected(self):
        opener = FakeOpener([FakeResponse(raw=b"x" * (_MAX_RESPONSE_BYTES_V1 + 1))])
        adapter = Selma0GitHubAdapterAndroidV1(repo_spec="example/repo", opener=opener)
        with self.assertRaises(RuntimeError):
            adapter.repo_summary()

    def test_redirect_handler_fails_closed(self):
        handler = _NoRedirectHandlerV1()
        request = urllib.request.Request("https://api.github.com/repos/example/repo")
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(
                request,
                io.BytesIO(b""),
                301,
                "Moved",
                {},
                "https://evil.example/repo",
            )

    def test_http_error_does_not_expose_token(self):
        error = urllib.error.HTTPError(
            "https://api.github.com/repos/example/repo",
            403,
            "Forbidden",
            {},
            io.BytesIO(json.dumps({"message": "permission denied"}).encode("utf-8")),
        )
        opener = FakeOpener([error])
        with patch.dict(os.environ, {"SELMA0_GITHUB_TOKEN_V1": "never-print-this"}, clear=True):
            adapter = Selma0GitHubAdapterAndroidV1(repo_spec="example/repo", opener=opener)
            with self.assertRaises(RuntimeError) as context:
                adapter.repo_summary()
        self.assertIn("HTTP 403", str(context.exception))
        self.assertNotIn("never-print-this", str(context.exception))

    def test_registered_tool_risks_are_fail_closed(self):
        plugins = Selma0PluginAdapterRegistryAndroidV1()
        tools = Selma0ToolRegistryAndroidV1()
        register_plugin_status_tool(tools, plugins)
        register_github_adapter_tools(
            tools,
            plugin_registry=plugins,
            adapter=Selma0GitHubAdapterAndroidV1(repo_spec="example/repo", opener=FakeOpener()),
        )
        self.assertEqual(tools.describe("plugins.status")["risk"], "sensitive_read")
        self.assertEqual(tools.describe("github.repo_summary")["risk"], "sensitive_read")
        self.assertEqual(tools.describe("github.list_issues")["risk"], "sensitive_read")
        self.assertEqual(tools.describe("github.create_issue")["risk"], "external_effect")


if __name__ == "__main__":
    unittest.main()
