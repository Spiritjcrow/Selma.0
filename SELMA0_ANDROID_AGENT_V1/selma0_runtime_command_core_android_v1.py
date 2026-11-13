#!/usr/bin/env python3
import ipaddress
import os
import signal
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import selma0_runtime_android_v1 as base
from selma0_command_router_android_v1 import Selma0CommandRouterAndroidV1
from selma0_selmasafe_registry_android_v1 import register_selmasafe_tools

REPLIKA_SKILL_DIR_V1 = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "skills",
    "replika_migration_v1",
)
if REPLIKA_SKILL_DIR_V1 not in sys.path:
    sys.path.insert(0, REPLIKA_SKILL_DIR_V1)

from replika_migration_v1 import register_replika_migration_tools


COMMAND_ROUTER_V1 = Selma0CommandRouterAndroidV1()
register_replika_migration_tools(COMMAND_ROUTER_V1.registry)
COMMAND_ROUTER_V1.registry.register(
    "selma.status",
    lambda: base.SELMA0_V1.status(),
    risk="read",
    description="Return the local Selma runtime status without modifying state.",
)
COMMAND_ROUTER_V1.registry.register(
    "selma.chat",
    lambda message="": base.SELMA0_V1.chat(message),
    risk="write",
    description="Send a user-approved chat turn through Selma.0; this writes conversation memory and may use the configured online fallback.",
)
COMMAND_ROUTER_V1.registry.register(
    "safety.record_incident",
    lambda summary="", details=None, source="user_report", confidence=None, include_device_snapshot=False: base.SAFETY_V1.record_incident(
        summary=summary,
        details=details,
        source=source,
        confidence=confidence,
        include_device_snapshot=bool(include_device_snapshot),
    ),
    risk="write",
    description="Record a user-authorized safety incident in the local safety audit.",
)
COMMAND_ROUTER_V1.registry.register(
    "safety.update_profile",
    lambda updates=None: base.SAFETY_V1.update_profile(updates or {}),
    risk="write",
    description="Update the local Selma safety profile after explicit approval.",
)
COMMAND_ROUTER_V1.registry.register(
    "safety.activate_sos",
    lambda reason="": base.SAFETY_V1.activate_sos(reason=reason, confirmed=True),
    risk="external_effect",
    description="Activate the user-confirmed local SOS workflow, which may send configured SMS messages.",
)
register_selmasafe_tools(COMMAND_ROUTER_V1.registry, base.SAFETY_V1)


def _allow_nonloopback_bind_v1():
    return os.getenv("SELMA0_ALLOW_NONLOOPBACK_V1", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _is_loopback_host_v1(host):
    value = str(host or "").strip()
    if value.lower() == "localhost":
        return True
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _validate_bind_host_v1(host):
    if _is_loopback_host_v1(host):
        return host
    if _allow_nonloopback_bind_v1():
        return host
    raise RuntimeError(
        "Refusing non-loopback Selma command-core bind. "
        "Keep SELMA0_HOST_V1 on 127.0.0.1/::1/localhost, or explicitly set "
        "SELMA0_ALLOW_NONLOOPBACK_V1=1 after applying an authenticated transport boundary."
    )


def _hostname_from_authority_v1(authority):
    value = str(authority or "").strip()
    if not value or any(ch in value for ch in "\r\n/\\"):
        return ""
    try:
        parsed = urlsplit("//" + value)
        return str(parsed.hostname or "").strip().lower()
    except (TypeError, ValueError):
        return ""


def _configured_allowed_hosts_v1():
    hosts = {"localhost"}
    bind_host = str(base.SELMA0_HOST_V1 or "").strip().strip("[]").lower()
    if bind_host:
        hosts.add(bind_host)
    for value in os.getenv("SELMA0_ALLOWED_HTTP_HOSTS_V1", "").split(","):
        value = value.strip().strip("[]").lower()
        if value:
            hosts.add(value)
    return hosts


def _is_allowed_http_host_v1(host_header):
    hostname = _hostname_from_authority_v1(host_header)
    if not hostname:
        return False
    if _is_loopback_host_v1(hostname):
        return True
    if not _allow_nonloopback_bind_v1():
        return False
    return hostname in _configured_allowed_hosts_v1()


def _is_allowed_origin_v1(origin_header):
    value = str(origin_header or "").strip()
    if not value:
        return True
    if value.lower() == "null":
        return False
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    if _is_loopback_host_v1(hostname):
        return True
    if not _allow_nonloopback_bind_v1():
        return False
    return hostname in _configured_allowed_hosts_v1()


def _legacy_api_passthrough_allowed_v1(method, path):
    """Fail closed: command-core API routes must be handled explicitly above."""
    return False


def _http_status_for_result(result):
    if result.get("ok") is True:
        return 200
    if result.get("requires_approval") is True:
        return 409
    return 400


class Selma0CommandCoreHTTPAndroidV1(base.Selma0HTTPAndroidV1):
    def _enforce_http_boundary_v1(self, require_origin=False):
        if not _is_allowed_http_host_v1(self.headers.get("Host")):
            self.send_json(403, {"error": "untrusted Host header"})
            return False
        if require_origin and not _is_allowed_origin_v1(self.headers.get("Origin")):
            self.send_json(403, {"error": "cross-origin request rejected"})
            return False
        return True

    def do_GET(self):
        if not self._enforce_http_boundary_v1(require_origin=False):
            return
        if self.path == "/api/selma0/status/v1":
            status = base.SELMA0_V1.status()
            status["command_core"] = COMMAND_ROUTER_V1.status()
            self.send_json(200, status)
            return
        if self.path == "/api/selma0/tools/v1":
            self.send_json(200, COMMAND_ROUTER_V1.status())
            return
        if self.path == "/api/selma0/tools/audit/v1":
            self.send_json(200, {"events": COMMAND_ROUTER_V1.audit.recent(100)})
            return
        if self.path.startswith("/api/selma0/"):
            self.send_json(404, {"error": "API route not registered in command core"})
            return
        return super().do_GET()

    def do_POST(self):
        if not self._enforce_http_boundary_v1(require_origin=True):
            return
        if self.path == "/api/selma0/tools/execute/v1":
            try:
                body = self.read_json_body()
                arguments = body.get("arguments", {})
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be an object")
                result = COMMAND_ROUTER_V1.execute(
                    tool_name=body.get("tool", ""),
                    arguments=arguments,
                    approved=body.get("approved") is True,
                    request_id=body.get("request_id"),
                )
                self.send_json(_http_status_for_result(result), result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if self.path == "/api/selma0/chat/v1":
            try:
                body = self.read_json_body()
                message = str(body.get("message", "")).strip()
                if not message:
                    raise ValueError("message is required")
                result = COMMAND_ROUTER_V1.execute(
                    "selma.chat",
                    {"message": message},
                    approved=body.get("confirmed") is True,
                    request_id=body.get("request_id"),
                )
                self.send_json(_http_status_for_result(result), result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if self.path == "/api/selma0/replika/preview/v1":
            try:
                body = self.read_json_body()
                source = str(body.get("source", "")).strip()
                if not source:
                    raise ValueError("source is required")
                result = COMMAND_ROUTER_V1.execute(
                    "replika.preview_archive",
                    {
                        "source": source,
                        "companion_name": str(body.get("companion_name", "Selma")),
                    },
                    approved=False,
                    request_id=body.get("request_id"),
                )
                self.send_json(_http_status_for_result(result), result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if self.path == "/api/selma0/replika/import/v1":
            try:
                body = self.read_json_body()
                source = str(body.get("source", "")).strip()
                if not source:
                    raise ValueError("source is required")
                result = COMMAND_ROUTER_V1.execute(
                    "replika.import_archive",
                    {
                        "source": source,
                        "companion_name": str(body.get("companion_name", "Selma")),
                        "db_path": base.MEMORY_V1.db_path,
                        "dry_run": False,
                    },
                    approved=body.get("confirmed") is True,
                    request_id=body.get("request_id"),
                )
                status = 201 if result.get("ok") is True else _http_status_for_result(result)
                self.send_json(status, result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if self.path == "/api/selma0/safety/incident/v1":
            try:
                body = self.read_json_body()
                result = COMMAND_ROUTER_V1.execute(
                    "safety.record_incident",
                    {
                        "summary": body.get("summary", ""),
                        "details": body.get("details"),
                        "source": body.get("source", "user_report"),
                        "confidence": body.get("confidence"),
                        "include_device_snapshot": bool(body.get("include_device_snapshot", False)),
                    },
                    approved=True,
                    request_id=body.get("request_id"),
                )
                status = 201 if result.get("ok") is True else _http_status_for_result(result)
                self.send_json(status, result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if self.path == "/api/selma0/safety/profile/v1":
            try:
                body = self.read_json_body()
                updates = dict(body)
                updates.pop("confirmed", None)
                updates.pop("request_id", None)
                result = COMMAND_ROUTER_V1.execute(
                    "safety.update_profile",
                    {"updates": updates},
                    approved=body.get("confirmed") is True,
                    request_id=body.get("request_id"),
                )
                self.send_json(_http_status_for_result(result), result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if self.path == "/api/selma0/safety/sos/v1":
            try:
                body = self.read_json_body()
                result = COMMAND_ROUTER_V1.execute(
                    "safety.activate_sos",
                    {"reason": body.get("reason", "")},
                    approved=body.get("confirmed") is True,
                    request_id=body.get("request_id"),
                )
                self.send_json(_http_status_for_result(result), result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if self.path.startswith("/api/selma0/") and not _legacy_api_passthrough_allowed_v1("POST", self.path):
            self.send_json(404, {"error": "API route not registered in command core"})
            return
        return super().do_POST()


def main():
    bind_host = _validate_bind_host_v1(base.SELMA0_HOST_V1)
    server = ThreadingHTTPServer(
        (bind_host, base.SELMA0_PORT_V1),
        Selma0CommandCoreHTTPAndroidV1,
    )
    print(
        f"[Selma.0] Command Core active at "
        f"http://{bind_host}:{base.SELMA0_PORT_V1}"
    )
    print(f"[Selma.0] Memory: {base.MEMORY_V1.db_path}")
    print(f"[Selma.0] Command audit: {COMMAND_ROUTER_V1.audit.path}")
    print(f"[Selma.0] Registered tools: {len(COMMAND_ROUTER_V1.registry.list_public())}")

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    server.serve_forever()
    server.server_close()


if __name__ == "__main__":
    main()
