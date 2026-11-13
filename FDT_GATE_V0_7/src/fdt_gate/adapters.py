from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .models import ActionEnvelope


class AdapterError(RuntimeError):
    pass


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, Callable[[ActionEnvelope], Any]] = {}

    def register(self, effect: str, fn: Callable[[ActionEnvelope], Any]) -> None:
        if effect in self._adapters:
            raise ValueError(f"adapter already registered: {effect}")
        self._adapters[effect] = fn

    def execute(self, action: ActionEnvelope) -> Any:
        fn = self._adapters.get(action.effect)
        if fn is None:
            raise AdapterError(f"no adapter for effect {action.effect}")
        return fn(action)


class FilesystemAdapter:
    def __init__(self, root: str | Path, resource_prefix: str = "workspace/"):
        self.root = Path(root).resolve()
        self.prefix = resource_prefix
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, resource: str) -> Path:
        if not resource.startswith(self.prefix):
            raise AdapterError("resource outside filesystem namespace")
        rel = resource[len(self.prefix):]
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise AdapterError("path traversal denied")
        return candidate

    def read(self, action: ActionEnvelope) -> dict[str, Any]:
        p = self._path(action.resource)
        data = p.read_bytes()
        max_bytes = int(action.payload.get("max_bytes", 1_000_000))
        if len(data) > max_bytes:
            raise AdapterError("read exceeds max_bytes")
        return {"path": str(p.relative_to(self.root)), "text": data.decode("utf-8"), "bytes": len(data)}

    def write(self, action: ActionEnvelope) -> dict[str, Any]:
        p = self._path(action.resource)
        text = action.payload.get("text")
        if not isinstance(text, str):
            raise AdapterError("fs.write requires payload.text string")
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".fdt-", dir=str(p.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return {"path": str(p.relative_to(self.root)), "bytes": len(text.encode("utf-8"))}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPAdapter:
    def __init__(self, allowed_hosts: set[str], timeout: float = 10.0):
        self.allowed_hosts = set(allowed_hosts)
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect())

    def request(self, action: ActionEnvelope) -> dict[str, Any]:
        u = urllib.parse.urlsplit(action.resource)
        if u.scheme not in {"https"} or not u.hostname or u.hostname not in self.allowed_hosts:
            raise AdapterError("HTTP target not allowlisted or not HTTPS")
        method = action.method.upper()
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
            raise AdapterError("HTTP method denied")
        body = action.payload.get("body")
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(action.resource, data=data, method=method)
        for k, v in action.payload.get("headers", {}).items():
            if k.lower() in {"host", "content-length", "connection"}:
                raise AdapterError(f"header denied: {k}")
            req.add_header(k, str(v))
        with self._opener.open(req, timeout=self.timeout) as resp:
            content = resp.read(1_000_001)
            if len(content) > 1_000_000:
                raise AdapterError("HTTP response exceeds 1MB")
            return {"status": resp.status, "body": content.decode("utf-8", "replace")}


class GitAdapter:
    def __init__(self, repo_root: str | Path, resource_prefix: str = "repo/"):
        self.root = Path(repo_root).resolve()
        self.prefix = resource_prefix
        if not (self.root / ".git").exists():
            raise AdapterError("repo_root is not a Git repository")

    def _run(self, args: list[str]) -> dict[str, Any]:
        cp = subprocess.run(
            ["git", "-C", str(self.root), *args], capture_output=True, text=True,
            timeout=15, check=False, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if cp.returncode != 0:
            raise AdapterError(cp.stderr.strip() or "git command failed")
        return {"stdout": cp.stdout, "stderr": cp.stderr, "code": cp.returncode}

    def status(self, action: ActionEnvelope) -> dict[str, Any]:
        return self._run(["status", "--porcelain=v1", "--untracked-files=all"])

    def diff(self, action: ActionEnvelope) -> dict[str, Any]:
        return self._run(["diff", "--no-ext-diff", "--"])
