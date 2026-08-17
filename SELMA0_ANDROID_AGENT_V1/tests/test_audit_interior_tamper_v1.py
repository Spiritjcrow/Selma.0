#!/usr/bin/env python3
import json
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


class InteriorAuditTamperTests(unittest.TestCase):
    def test_interior_tamper_blocks_approved_write_before_handler_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            audit = Selma0AuditLogAndroidV1(path=path)
            audit.append("first", {"value": "original"})
            audit.append("second", {"value": "tail remains structurally valid"})

            with open(path, "r", encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle if line.strip()]

            # Modify an interior event without recomputing its event hash. The
            # final row and final event_hash stay structurally valid, so a
            # tail-only integrity check would miss this alteration.
            rows[0]["details"]["value"] = "tampered"
            with open(path, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

            integrity = audit.verify_chain()
            self.assertFalse(integrity["ok"])
            self.assertEqual(integrity["error"], "event hash mismatch")

            calls = {"count": 0}

            def mutate(value=""):
                calls["count"] += 1
                return {"value": value}

            registry = Selma0ToolRegistryAndroidV1()
            registry.register("write.mutate", mutate, risk="write")
            router = Selma0CommandRouterAndroidV1(registry=registry, audit_log=audit)

            result = router.execute(
                "write.mutate",
                {"value": "must-not-run"},
                approved=True,
                request_id="interior-tamper-1",
            )

            self.assertFalse(result["ok"])
            self.assertEqual(
                result["error"],
                "audit chain integrity check failed; mutating execution blocked",
            )
            self.assertFalse(result["audit_chain"]["ok"])
            self.assertEqual(calls["count"], 0)


if __name__ == "__main__":
    unittest.main()
