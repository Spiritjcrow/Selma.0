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
from selma0_runtime_command_core_android_v1 import (
    COMMAND_ROUTER_V1,
    _hostname_from_authority_v1,
    _is_allowed_http_host_v1,
    _is_allowed_origin_v1,
    _is_loopback_host_v1,
    _validate_bind_host_v1,
)
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


class CommandCoreHTTPBoundaryTests(unittest.TestCase):
    def test_authority_parser_handles_ipv4_ipv6_and_rejects_malformed(self):
        self.assertEqual(_hostname_from_authority_v1("127.0.0.1:8765"), "127.0.0.1")
        self.assertEqual(_hostname_from_authority_v1("[::1]:8765"), "::1")
        self.assertEqual(_hostname_from_authority_v1("localhost:8765"), "localhost")
        self.assertEqual(_hostname_from_authority_v1("evil.example/path"), "")
        self.assertEqual(_hostname_from_authority_v1("evil.example\r\nX-Test: 1"), "")

    def test_loopback_host_headers_are_allowed(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SELMA0_ALLOW_NONLOOPBACK_V1", None)
            for host in ("127.0.0.1:8765", "localhost:8765", "[::1]:8765"):
                with self.subTest(host=host):
                    self.assertTrue(_is_allowed_http_host_v1(host))

    def test_dns_rebinding_host_fails_closed_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SELMA0_ALLOW_NONLOOPBACK_V1", None)
            self.assertFalse(_is_allowed_http_host_v1("attacker.example"))
            self.assertFalse(_is_allowed_http_host_v1("192.168.1.10:8765"))
            self.assertFalse(_is_allowed_http_host_v1(""))

    def test_browser_origin_fails_closed_for_nonloopback_origin(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SELMA0_ALLOW_NONLOOPBACK_V1", None)
            self.assertTrue(_is_allowed_origin_v1(None))
            self.assertTrue(_is_allowed_origin_v1("http://127.0.0.1:8765"))
            self.assertTrue(_is_allowed_origin_v1("http://localhost:8765"))
            self.assertFalse(_is_allowed_origin_v1("https://attacker.example"))
            self.assertFalse(_is_allowed_origin_v1("null"))

    def test_explicit_nonloopback_http_host_allowlist_is_required(self):
        env = {
            "SELMA0_ALLOW_NONLOOPBACK_V1": "1",
            "SELMA0_ALLOWED_HTTP_HOSTS_V1": "selma.example,192.168.1.20",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(_is_allowed_http_host_v1("selma.example:8765"))
            self.assertTrue(_is_allowed_origin_v1("https://selma.example"))
            self.assertFalse(_is_allowed_http_host_v1("attacker.example:8765"))
            self.assertFalse(_is_allowed_origin_v1("https://attacker.example"))


class CommandCoreSafetyPolicyTests(unittest.TestCase):
    def test_safety_mutations_are_registered_with_fail_closed_risks(self):
        self.assertEqual(COMMAND_ROUTER_V1.registry.describe("safety.record_incident")["risk"], "write")
        self.assertEqual(COMMAND_ROUTER_V1.registry.describe("safety.update_profile")["risk"], "write")
        self.assertEqual(COMMAND_ROUTER_V1.registry.describe("safety.activate_sos")["risk"], "external_effect")

    def test_safety_mutations_require_approval_before_execution(self):
        for tool_name, arguments in (
            ("safety.record_incident", {"summary": "test"}),
            ("safety.update_profile", {"updates": {"send_sms_on_sos": False}}),
            ("safety.activate_sos", {"reason": "test"}),
        ):
            with self.subTest(tool=tool_name):
                result = COMMAND_ROUTER_V1.execute(tool_name, arguments, approved=False)
                self.assertFalse(result["ok"])
                self.assertTrue(result["requires_approval"])


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

    def test_router_rejects_non_object_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Selma0AuditLogAndroidV1(path=os.path.join(tmp, "audit.jsonl"))
            registry = Selma0ToolRegistryAndroidV1()
            calls = {"count": 0}

            def handler(**kwargs):
                calls["count"] += 1
                return kwargs

            registry.register("read.echo", handler, risk="read")
            router = Selma0CommandRouterAndroidV1(registry=registry, audit_log=audit)
            result = router.execute("read.echo", ["not", "an", "object"])

            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "arguments must be an object")
            self.assertEqual(calls["count"], 0)
            events = audit.request_events(result["request_id"])
            self.assertTrue(any(e["event_type"] == "tool_rejected" for e in events))

    def test_write_request_id_is_idempotent_across_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Selma0AuditLogAndroidV1(path=os.path.join(tmp, "audit.jsonl"))
            registry = Selma0ToolRegistryAndroidV1()
            calls = {"count": 0}

            def mutate(value=""):
                calls["count"] += 1
                return {"value": value, "call": calls["count"]}

            registry.register("write.once", mutate, risk="write")
            router = Selma0CommandRouterAndroidV1(registry=registry, audit_log=audit)
            request_id = "retry-safe-1"

            first = router.execute("write.once", {"value": "x"}, approved=True, request_id=request_id)
            second = router.execute("write.once", {"value": "x"}, approved=True, request_id=request_id)

            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertTrue(second["replayed"])
            self.assertEqual(first["result"], second["result"])
            self.assertEqual(calls["count"], 1)
            self.assertTrue(any(e["event_type"] == "tool_replay_suppressed" for e in audit.request_events(request_id)))


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
