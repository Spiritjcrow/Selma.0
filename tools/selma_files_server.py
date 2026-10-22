"""Zero-dependency, loopback-only dual-pane file browser for SelmaOS."""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from core.universal_files import FileBoundaryError, LocalFileProvider  # noqa: E402

PAGE = PROJECT / 'webui' / 'selma_files' / 'index.html'



def parse_operation_payload(payload: bytes) -> dict:
    """Parse operation JSON without allowing non-object top-level values."""
    request = json.loads(payload)
    if not isinstance(request, dict):
        raise FileBoundaryError('JSON object required')
    return request


def public_error(exc: Exception) -> str:
    """Return a bounded API error without host paths or OS details."""
    if isinstance(exc, FileBoundaryError):
        return str(exc)
    if isinstance(exc, FileExistsError):
        return 'destination already exists'
    if isinstance(exc, FileNotFoundError):
        return 'item not found'
    if isinstance(exc, PermissionError):
        return 'permission denied'
    if isinstance(exc, (KeyError, TypeError, ValueError)):
        return 'invalid request'
    return 'operation failed'



def serve(root: str, port: int = 8766) -> None:
    provider = LocalFileProvider(root)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def _valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def _send(self, status: int, content: bytes, content_type: str):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def _json(self, status: int, body: dict):
            self._send(status, json.dumps(body).encode('utf-8'), 'application/json; charset=utf-8')

        def do_GET(self):
            if not self._valid_host():
                return self._json(403, {'error': 'invalid host'})
            parts = urlsplit(self.path)
            if parts.path == '/':
                return self._send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
            if parts.path == '/api/session':
                return self._json(200, {'token': token})
            if parts.path == '/api/list':
                if not secrets.compare_digest(self.headers.get('X-Selma-Token', ''), token):
                    return self._json(403, {'error': 'invalid session'})
                try:
                    name = parse_qs(parts.query).get('path', [''])[0]
                    return self._json(200, provider.list_dir(name))
                except (ValueError, FileNotFoundError, PermissionError, OSError) as exc:
                    return self._json(400, {'error': public_error(exc)})
            self._json(404, {'error': 'not found'})

        def do_POST(self):
            if not self._valid_host():
                return self._json(403, {'error': 'invalid host'})
            if urlsplit(self.path).path != '/api/operation':
                return self._json(404, {'error': 'not found'})
            if (self.headers.get('Origin') != f'http://127.0.0.1:{port}' and
                    self.headers.get('Origin') != f'http://localhost:{port}'):
                return self._json(403, {'error': 'invalid origin'})
            if not secrets.compare_digest(self.headers.get('X-Selma-Token', ''), token):
                return self._json(403, {'error': 'invalid session'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self._json(415, {'error': 'JSON required'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 2 or length > 4096:
                    return self._json(413, {'error': 'invalid request size'})
                request = parse_operation_payload(self.rfile.read(length))
                action = request.get('action')
                if action == 'copy':
                    result = provider.copy_file(request['source'], request['destination'])
                elif action == 'move':
                    result = provider.move_file(request['source'], request['destination'])
                elif action == 'mkdir':
                    result = provider.mkdir(request['destination'], request['name'])
                else:
                    raise FileBoundaryError('unknown operation')
                return self._json(200, result)
            except (ValueError, KeyError, TypeError, FileNotFoundError, FileExistsError, PermissionError, OSError) as exc:
                return self._json(400, {'error': public_error(exc)})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Selma Universal Files: http://127.0.0.1:{port} (root: {provider.root})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SelmaOS local dual-pane file manager')
    parser.add_argument('--root', default='.', help='Only folder the application may access')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    serve(args.root, args.port)

