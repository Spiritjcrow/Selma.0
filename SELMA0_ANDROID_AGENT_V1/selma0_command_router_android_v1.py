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

    def status(self):
        return {
            "tool_count": len(self.registry.list_public()),
            "tools": self.registry.list_public(),
            "permission_policy": self.permissions.status(),
            "audit_path": self.audit.path,
            "audit_chain": self.audit.verify_chain(),
        }

    def execute(self, tool_name, arguments=None, approved=False, request_id=None):
        request_id = str(request_id or uuid.uuid4())
        tool_name = str(tool_name or "").strip()
        arguments = arguments if isinstance(arguments, dict) else {}

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
