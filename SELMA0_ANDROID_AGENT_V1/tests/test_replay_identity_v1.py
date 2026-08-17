#!/usr/bin/env python3
import os
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from selma0_audit_log_android_v1 import Selma0AuditLogAndroidV1
from selma0_command_router_android_v1 import Selma0CommandRouterAndroidV1
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1


class ReplayIdentityTests(unittest.TestCase):
    def _router(self, root, calls):
        audit = Selma0AuditLogAndroidV1(path=os.path.join(root, "audit.jsonl"))
        registry = Selma0ToolRegistryAndroidV1()

        def mutate(value="", nested=None):
            calls["count"] += 1
            return {"value": value, "nested": nested, "call": calls["count"]}

        registry.register("write.once", mutate, risk="write")
        return Selma0CommandRouterAndroidV1(registry=registry, audit_log=audit), audit

    def test_same_request_same_arguments_replays_original_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = {"count": 0}
            router, _ = self._router(tmp, calls)
            request_id = "same-args"

            first = router.execute(
                "write.once",
                {"value": "x", "nested": {"b": 2, "a": 1}},
                approved=True,
                request_id=request_id,
            )
            second = router.execute(
                "write.once",
                {"nested": {"a": 1, "b": 2}, "value": "x"},
                approved=True,
                request_id=request_id,
            )

            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertTrue(second["replayed"])
            self.assertEqual(first["result"], second["result"])
            self.assertEqual(calls["count"], 1)

    def test_same_request_different_arguments_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = {"count": 0}
            router, audit = self._router(tmp, calls)
            request_id = "different-args"

            first = router.execute(
                "write.once",
                {"value": "first"},
                approved=True,
                request_id=request_id,
            )
            second = router.execute(
                "write.once",
                {"value": "second"},
                approved=True,
                request_id=request_id,
            )

            self.assertTrue(first["ok"])
            self.assertFalse(second["ok"])
            self.assertEqual(second["error"], "request_id already completed with different arguments")
            self.assertEqual(calls["count"], 1)

            events = audit.request_events(request_id)
            replay_events = [e for e in events if e.get("event_type") == "tool_replay_suppressed"]
            self.assertEqual(len(replay_events), 1)
            self.assertFalse(replay_events[0]["details"]["replay_ok"])

    def test_non_json_serializable_arguments_are_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = {"count": 0}
            router, _ = self._router(tmp, calls)

            result = router.execute(
                "write.once",
                {"value": {1, 2, 3}},
                approved=True,
                request_id="non-json",
            )

            self.assertFalse(result["ok"])
            self.assertIn("arguments must be JSON-serializable", result["error"])
            self.assertEqual(calls["count"], 0)


if __name__ == "__main__":
    unittest.main()
