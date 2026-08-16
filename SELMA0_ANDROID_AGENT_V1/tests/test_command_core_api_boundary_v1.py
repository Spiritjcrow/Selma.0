#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_runtime_command_core_android_v1 import (
    COMMAND_ROUTER_V1,
    _legacy_api_passthrough_allowed_v1,
)


class CommandCoreLegacyAPIBoundaryTests(unittest.TestCase):
    def test_no_legacy_api_passthrough_remains(self):
        routes = (
            ("POST", "/api/selma0/chat/v1"),
            ("GET", "/api/selma0/memory/v1"),
            ("GET", "/api/selma0/safety/status/v1"),
            ("GET", "/api/selma0/safety/events/v1"),
            ("POST", "/api/selma0/replika/import/v1"),
            ("POST", "/api/selma0/safety/profile/v1"),
            ("POST", "/api/selma0/safety/sos/v1"),
            ("POST", "/api/selma0/future-mutation/v1"),
        )
        for method, path in routes:
            with self.subTest(method=method, path=path):
                self.assertFalse(_legacy_api_passthrough_allowed_v1(method, path))

    def test_chat_is_registered_as_approved_write_capability(self):
        descriptor = COMMAND_ROUTER_V1.registry.describe("selma.chat")
        self.assertEqual(descriptor["risk"], "write")

        denied = COMMAND_ROUTER_V1.permissions.evaluate(descriptor, approved=False)
        self.assertFalse(denied.allowed)
        self.assertTrue(denied.requires_approval)

        allowed = COMMAND_ROUTER_V1.permissions.evaluate(descriptor, approved=True)
        self.assertTrue(allowed.allowed)

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
