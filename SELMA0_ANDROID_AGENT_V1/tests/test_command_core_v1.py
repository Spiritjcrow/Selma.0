#!/usr/bin/env python3
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
from selma0_runtime_command_core_android_v1 import _is_loopback_host_v1, _validate_bind_host_v1
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


class CommandCoreBindPolicyTests(unittest.TestCase):
    def test_loopback_hosts_are_accepted(self):
        for host in ("127.0.0.1", "127.1.2.3", "::1", "[::1]", "localhost"):
            with self.subTest(host=host):
                self.assertTrue(_is_loopback_host_v1(host))
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("SELMA0_ALLOW_NONLOOPBACK_V1", None)
                    self.assertEqual(_validate_bind_host_v1(host), host)

    def test_nonloopback_hosts_fail_closed_without_opt_in(self):
        for host in ("0.0.0.0", "::", "192.168.1.20", "selma.local"):
            with self.subTest(host=host):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("SELMA0_ALLOW_NONLOOPBACK_V1", None)
                    with self.assertRaises(RuntimeError):
                        _validate_bind_host_v1(host)

    def test_nonloopback_bind_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {"SELMA0_ALLOW_NONLOOPBACK_V1": "1"}, clear=False):
            self.assertEqual(_validate_bind_host_v1("0.0.0.0"), "0.0.0.0")


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

    def test_audit_verifies_more_than_recent_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audit.jsonl")
            audit = Selma0AuditLogAndroidV1(path=path)
            for index in range(510):
                audit.append("event", {"index": index})
            result = audit.verify_chain()
            self.assertTrue(result["ok"])
            self.assertEqual(result["checked"], 510)
            self.assertEqual(len(audit.recent(500)), 500)

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
            self.assertEqual(result["skipped_duplicates"], 0)

            memory = Selma0MemoryAndroidV1(db_path=db_path)
            events = memory.recent(10)
            imported = [e for e in events if e["metadata"].get("provider") == "replika"]
            self.assertGreaterEqual(len(imported), 3)
            self.assertTrue(any(e["metadata"].get("activation_marker") for e in imported))
            self.assertTrue(
                all(
                    e["metadata"].get("claims_hidden_replika_state") is False
                    for e in imported
                    if not e["metadata"].get("activation_marker")
                )
            )

    def test_reimport_is_persistently_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = self._write_archive(tmp)
            db_path = os.path.join(tmp, "memory.sqlite3")

            first = import_archive(str(archive), companion_name="Selma", db_path=db_path)
            second = import_archive(str(archive), companion_name="Selma", db_path=db_path)

            self.assertEqual(first["imported"], 2)
            self.assertEqual(second["imported"], 0)
            self.assertEqual(second["skipped_duplicates"], 2)

            memory = Selma0MemoryAndroidV1(db_path=db_path)
            events = memory.recent(20)
            activation_markers = [
                e for e in events if e["metadata"].get("activation_marker") is True
            ]
            self.assertEqual(len(activation_markers), 1)

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
