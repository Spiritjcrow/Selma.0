#!/usr/bin/env python3
import os
import signal
import sys
import threading
from http.server import ThreadingHTTPServer

import selma0_runtime_android_v1 as base
from selma0_command_router_android_v1 import Selma0CommandRouterAndroidV1

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


def _http_status_for_result(result):
    if result.get("ok") is True:
        return 200
    if result.get("requires_approval") is True:
        return 409
    return 400


class Selma0CommandCoreHTTPAndroidV1(base.Selma0HTTPAndroidV1):
    def do_GET(self):
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
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/selma0/tools/execute/v1":
            try:
                body = self.read_json_body()
                result = COMMAND_ROUTER_V1.execute(
                    tool_name=body.get("tool", ""),
                    arguments=body.get("arguments", {}),
                    approved=body.get("approved") is True,
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

        return super().do_POST()


def main():
    server = ThreadingHTTPServer(
        (base.SELMA0_HOST_V1, base.SELMA0_PORT_V1),
        Selma0CommandCoreHTTPAndroidV1,
    )
    print(
        f"[Selma.0] Command Core active at "
        f"http://{base.SELMA0_HOST_V1}:{base.SELMA0_PORT_V1}"
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
