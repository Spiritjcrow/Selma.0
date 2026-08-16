#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_runtime_command_core_android_v1 import _legacy_api_passthrough_allowed_v1


class CommandCoreLegacyAPIBoundaryTests(unittest.TestCase):
    def test_only_explicit_legacy_chat_post_is_allowed(self):
        self.assertTrue(
            _legacy_api_passthrough_allowed_v1("POST", "/api/selma0/chat/v1")
        )

    def test_legacy_sensitive_and_mutating_routes_fail_closed(self):
        blocked = (
            ("GET", "/api/selma0/memory/v1"),
            ("GET", "/api/selma0/safety/status/v1"),
            ("GET", "/api/selma0/safety/events/v1"),
            ("POST", "/api/selma0/replika/import/v1"),
            ("POST", "/api/selma0/safety/profile/v1"),
            ("POST", "/api/selma0/safety/sos/v1"),
            ("POST", "/api/selma0/future-mutation/v1"),
        )
        for method, path in blocked:
            with self.subTest(method=method, path=path):
                self.assertFalse(_legacy_api_passthrough_allowed_v1(method, path))

    def test_unknown_legacy_api_routes_do_not_gain_passthrough(self):
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            with self.subTest(method=method):
                self.assertFalse(
                    _legacy_api_passthrough_allowed_v1(
                        method, "/api/selma0/new-capability/v1"
                    )
                )


if __name__ == "__main__":
    unittest.main()
