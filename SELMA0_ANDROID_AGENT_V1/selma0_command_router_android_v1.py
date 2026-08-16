import threading
import traceback
import uuid

from selma0_audit_log_android_v1 import Selma0AuditLogAndroidV1
from selma0_permission_engine_android_v1 import Selma0PermissionEngineAndroidV1
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1


class Selma0CommandRouterAndroidV1:
    """Permissioned command router for bounded Selma tools."""

    def __init__(self, registry=None, permission_engine=None, audit_log=None):
        self.registry = registry or Selma0ToolRegistryAndroidV1()
        self.permissions = permission_engine or Selma0PermissionEngineAndroidV1()
        self.audit = audit_log or Selma0AuditLogAndroidV1()
        self._execute_lock = threading.RLock()

    def status(self):
        return {
            "tool_count": len(self.registry.list_public()),
            "tools": self.registry.list_public(),
            "permission_policy": self.permissions.status(),
            "audit_path": self.audit.path,
            "audit_chain": self.audit.verify_chain(),
        }

    def _normalize_request_id(self, request_id):
        value = str(request_id or uuid.uuid4()).strip()
        if not value:
            value = str(uuid.uuid4())
        if len(value) > 128:
            raise ValueError("request_id exceeds 128 characters")
        return value

    def _completed_replay(self, request_id, tool_name):
        events = self.audit.request_events(request_id)
        completed = [event for event in events if event.get("event_type") == "tool_completed"]
        if not completed:
            return None
        latest = completed[-1]
        previous_tool = str(latest.get("details", {}).get("tool", ""))
        if previous_tool != tool_name:
            return {
                "ok": False,
                "request_id": request_id,
                "tool": tool_name,
                "error": "request_id already completed for a different tool",
            }
        return {
            "ok": True,
            "request_id": request_id,
            "tool": tool_name,
            "replayed": True,
            "result": latest.get("details", {}).get("result"),
        }

    def execute(self, tool_name, arguments=None, approved=False, request_id=None):
        try:
            request_id = self._normalize_request_id(request_id)
        except ValueError as exc:
            return {
                "ok": False,
                "request_id": None,
                "tool": str(tool_name or "").strip(),
                "error": str(exc),
            }

        tool_name = str(tool_name or "").strip()
        if arguments is None:
            arguments = {}
        elif not isinstance(arguments, dict):
            self.audit.append(
                "tool_rejected",
                {
                    "tool": tool_name,
                    "reason": "arguments must be an object",
                    "argument_type": type(arguments).__name__,
                },
                request_id=request_id,
            )
            return {
                "ok": False,
                "request_id": request_id,
                "tool": tool_name,
                "error": "arguments must be an object",
            }

        descriptor = self.registry.describe(tool_name)
        if descriptor is None:
            self.audit.append(
                "tool_rejected",
                {"tool": tool_name, "reason": "unknown tool", "arguments": arguments},
                request_id=request_id,
            )
            return {
                "ok": False,
                "request_id": request_id,
                "tool": tool_name,
                "error": "unknown tool",
            }

        decision = self.permissions.evaluate(descriptor, approved=approved)
        self.audit.append(
            "tool_authorization",
            {
                "tool": tool_name,
                "risk": decision.risk,
                "allowed": decision.allowed,
                "requires_approval": decision.requires_approval,
                "reason": decision.reason,
                "arguments": arguments,
            },
            request_id=request_id,
        )

        if not decision.allowed:
            return {
                "ok": False,
                "request_id": request_id,
                "tool": tool_name,
                "requires_approval": decision.requires_approval,
                "risk": decision.risk,
                "error": decision.reason,
            }

        with self._execute_lock:
            if decision.risk in {"write", "external_effect"}:
                replay = self._completed_replay(request_id, tool_name)
                if replay is not None:
                    self.audit.append(
                        "tool_replay_suppressed",
                        {"tool": tool_name, "risk": decision.risk},
                        request_id=request_id,
                    )
                    return replay

            try:
                result = self.registry.execute_handler(tool_name, arguments)
            except TypeError as exc:
                self.audit.append(
                    "tool_failed",
                    {"tool": tool_name, "error_type": "invalid_arguments", "error": str(exc)},
                    request_id=request_id,
                )
                return {
                    "ok": False,
                    "request_id": request_id,
                    "tool": tool_name,
                    "error": f"invalid tool arguments: {exc}",
                }
            except Exception as exc:
                self.audit.append(
                    "tool_failed",
                    {
                        "tool": tool_name,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "trace_tail": traceback.format_exc(limit=3),
                    },
                    request_id=request_id,
                )
                return {
                    "ok": False,
                    "request_id": request_id,
                    "tool": tool_name,
                    "error": str(exc),
                }

            self.audit.append(
                "tool_completed",
                {"tool": tool_name, "result": result},
                request_id=request_id,
            )
            return {
                "ok": True,
                "request_id": request_id,
                "tool": tool_name,
                "result": result,
            }
