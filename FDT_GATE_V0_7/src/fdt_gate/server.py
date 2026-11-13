from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .gate import FDTGate
from .models import ActionEnvelope


class TokenPrincipalMap:
    """Bearer-token to principal mapping; only SHA-256 token hashes are retained."""
    def __init__(self, mapping: dict[str, str]):
        self.mapping = dict(mapping)

    @staticmethod
    def digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def resolve(self, token: str) -> str | None:
        return self.mapping.get(self.digest(token))


def serve(gate: FDTGate, token_map: TokenPrincipalMap, bind: str = "127.0.0.1", port: int = 8767) -> None:
    class Handler(BaseHTTPRequestHandler):
        server_version = "FDTGate/0.7"

        def _json(self, status: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _principal(self) -> str | None:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return None
            return token_map.resolve(auth[7:])

        def do_GET(self):
            if self.path == "/healthz":
                self._json(200, {"ok": True, "service": "fdt-gate", "version": "0.7.0"})
            else:
                self._json(404, {"error": "not_found"})

        def do_POST(self):
            principal = self._principal()
            if principal is None:
                self._json(401, {"error": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("invalid content length")
                body = json.loads(self.rfile.read(length))
                action = ActionEnvelope.from_dict(body)
                if action.actor != principal:
                    self._json(403, {"error": "principal_mismatch"})
                    return
                if self.path == "/v1/authorize":
                    self._json(200, gate.authorize(action).to_dict())
                elif self.path == "/v1/execute":
                    result = gate.execute(action)
                    self._json(200 if result["executed"] else 403, result)
                else:
                    self._json(404, {"error": "not_found"})
            except Exception as exc:
                self._json(400, {"error": "bad_request", "detail": str(exc)})

        def log_message(self, format, *args):
            return

    ThreadingHTTPServer((bind, port), Handler).serve_forever()
