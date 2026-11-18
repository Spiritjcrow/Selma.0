from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
import os, subprocess, tempfile, uuid

@dataclass(slots=True)
class SandboxResult:
    run_id: str
    command: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    cwd: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict:
        return asdict(self)

class VirtualSandbox:
    DEFAULT_ENV_ALLOW = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "PYTHONPATH"}

    def __init__(self, timeout_seconds: int = 45):
        self.timeout_seconds = timeout_seconds

    def run(self, command: list[str], cwd: Path | None = None, env_allow: set[str] | None = None) -> SandboxResult:
        if not command: raise ValueError("command must not be empty")
        started = datetime.now(timezone.utc).isoformat()
        allow = env_allow or self.DEFAULT_ENV_ALLOW
        clean_env = {k: v for k, v in os.environ.items() if k in allow}
        tmp = tempfile.TemporaryDirectory(prefix="selma-sandbox-")
        run_cwd = Path(cwd).resolve() if cwd else Path(tmp.name)
        try:
            p = subprocess.run(command, cwd=run_cwd, env=clean_env, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
            result = SandboxResult(uuid.uuid4().hex, command, p.returncode, p.stdout, p.stderr, False, str(run_cwd), started, datetime.now(timezone.utc).isoformat())
        except subprocess.TimeoutExpired as exc:
            result = SandboxResult(uuid.uuid4().hex, command, None, (exc.stdout or "") if isinstance(exc.stdout, str) else "", (exc.stderr or "") if isinstance(exc.stderr, str) else "", True, str(run_cwd), started, datetime.now(timezone.utc).isoformat())
        finally:
            tmp.cleanup()
        return result
