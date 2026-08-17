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


class MutatingResultSerializationTests(unittest.TestCase):
    def test_unserializable_write_result_is_recorded_once_and_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Selma0AuditLogAndroidV1(path=os.path.join(tmp, "audit.jsonl"))
            registry = Selma0ToolRegistryAndroidV1()
            calls = {"count": 0}

            def mutate():
                calls["count"] += 1
                return {"non_json": {1, 2, 3}, "call": calls["count"]}

            registry.register("write.unserializable", mutate, risk="write")
            router = Selma0CommandRouterAndroidV1(registry=registry, audit_log=audit)
            request_id = "unserializable-result-1"

            first = router.execute("write.unserializable", approved=True, request_id=request_id)
            second = router.execute("write.unserializable", approved=True, request_id=request_id)

            self.assertTrue(first["ok"])
            self.assertTrue(first["result_serialization_warning"])
            self.assertEqual(first["result"]["result_type"], "dict")
            self.assertTrue(second["ok"])
            self.assertTrue(second["replayed"])
            self.assertEqual(first["result"], second["result"])
            self.assertEqual(calls["count"], 1)

            completed = [
                event
                for event in audit.request_events(request_id)
                if event.get("event_type") == "tool_completed"
            ]
            self.assertEqual(len(completed), 1)
            self.assertTrue(completed[0]["details"]["result_serialization_warning"])
            self.assertTrue(audit.verify_chain()["ok"])


if __name__ == "__main__":
    unittest.main()
