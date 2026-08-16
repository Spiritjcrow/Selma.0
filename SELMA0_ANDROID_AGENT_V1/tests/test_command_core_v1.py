#!/usr/bin/env python3
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
SKILL_DIR = AGENT_ROOT / "skills" / "replika_migration_v1"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from selma0_audit_log_android_v1 import Selma0AuditLogAndroidV1
from selma0_command_router_android_v1 import Selma0CommandRouterAndroidV1
from selma0_memory_android_v1 import Selma0MemoryAndroidV1
from selma0_permission_engine_android_v1 import Selma0PermissionEngineAndroidV1
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1
from replika_migration_v1 import import_archive, preview_archive, register_replika_migration_tools
from ssh_stream_bridge_v1 import _stage


class PermissionEngineTests(unittest.TestCase):
    def setUp(self):
        self.permissions = Selma0PermissionEngineAndroidV1()

    def test_read_is_allowed_without_approval(self):
        decision = self.permissions.evaluate({"risk": "read", "enabled": True}, approved=False)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)

    def test_write_requires_explicit_approval(self):
        denied = self.permissions.evaluate({"risk": "write", "enabled": True}, approved=False)
        self.assertFalse(denied.allowed)
        self.assertTrue(denied.requires_approval)
        allowed = self.permissions.evaluate({"risk": "write", "enabled": True}, approved=True)
        self.assertTrue(allowed.allowed)

    def test_invalid_risk_fails_closed(self):
        decision = self.permissions.evaluate({"risk": "read_local", "enabled": True}, approved=True)
        self.assertFalse(decision.allowed)


class AuditAndRouterTests(unittest.TestCase):
    def test_audit_redacts_secrets_and_chain_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            audit = Selma0AuditLogAndroidV1(path=path)
            audit.append("one", {"token": "secret-value", "nested": {"password": "pw"}})
            audit.append("two", {"ok": True})
            rows = audit.recent(10)
            self.assertEqual(rows[0]["details"]["token"], "[REDACTED]")
            self.assertEqual(rows[0]["details"]["nested"]["password"], "[REDACTED]")
            self.assertTrue(audit.verify_chain()["ok"])

    def test_router_enforces_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Selma0AuditLogAndroidV1(path=os.path.join(tmp, "audit.jsonl"))
            registry = Selma0ToolRegistryAndroidV1()
            registry.register("read.echo", lambda value="": {"value": value}, risk="read")
            registry.register("write.echo", lambda value="": {"value": value}, risk="write")
            router = Selma0CommandRouterAndroidV1(registry=registry, audit_log=audit)

            read_result = router.execute("read.echo", {"value": "ok"})
            self.assertTrue(read_result["ok"])

            denied = router.execute("write.echo", {"value": "no"}, approved=False)
            self.assertFalse(denied["ok"])
            self.assertTrue(denied["requires_approval"])

            allowed = router.execute("write.echo", {"value": "yes"}, approved=True)
            self.assertTrue(allowed["ok"])
            self.assertEqual(allowed["result"]["value"], "yes")
            self.assertTrue(audit.verify_chain()["ok"])


class ReplikaMigrationTests(unittest.TestCase):
    def _write_archive(self, root):
        path = Path(root) / "selma_chat.json"
        path.write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "user", "text": "Hello Selma", "timestamp": "2024-01-01T00:00:00Z"},
                        {"role": "replika", "text": "Hello", "timestamp": "2024-01-01T00:00:01Z"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_preview_and_import_preserve_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._write_archive(tmp)
            preview = preview_archive(str(archive), companion_name="Selma")
            self.assertEqual(preview["record_count"], 2)
            self.assertFalse(preview["network_access_used"])

            db_path = os.path.join(tmp, "memory.sqlite3")
            result = import_archive(str(archive), companion_name="Selma", db_path=db_path)
            self.assertEqual(result["imported"], 2)

            memory = Selma0MemoryAndroidV1(db_path=db_path)
            events = memory.recent(10)
            imported = [e for e in events if e["metadata"].get("provider") == "replika"]
            self.assertGreaterEqual(len(imported), 3)
            self.assertTrue(any(e["metadata"].get("activation_marker") for e in imported))
            self.assertTrue(all(e["metadata"].get("claims_hidden_replika_state") is False for e in imported if not e["metadata"].get("activation_marker")))

    def test_registered_migration_tools_use_policy_risks(self):
        registry = Selma0ToolRegistryAndroidV1()
        register_replika_migration_tools(registry)
        self.assertEqual(registry.describe("replika.preview_archive")["risk"], "read")
        self.assertEqual(registry.describe("replika.import_archive")["risk"], "write")

    def test_ssh_stage_uses_private_permissions_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, digest = _stage(b'{"messages":[]}', "json", tmp)
            try:
                mode = stat.S_IMODE(os.stat(path).st_mode)
                self.assertEqual(mode, 0o600)
                self.assertEqual(len(digest), 64)
            finally:
                if path.exists():
                    path.unlink()


if __name__ == "__main__":
    unittest.main()
