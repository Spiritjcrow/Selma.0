"""Bug Bounty Wrangler v0.1: offline-only scope gate. No network operations."""
from dataclasses import dataclass
from urllib.parse import urlsplit
import fnmatch
import hashlib
import json
import threading

@dataclass(frozen=True)
class ScopePolicy:
    allowed_hosts: tuple[str, ...]
    excluded_hosts: tuple[str, ...] = ()
    allowed_schemes: tuple[str, ...] = ("https",)
    allowed_ports: tuple[int, ...] = (443,)

def _host_match(host: str, pattern: str) -> bool:
    pattern = pattern.lower().rstrip(".")
    host = host.lower().rstrip(".")
    if pattern.startswith("*."):
        suffix = pattern[2:]
        return host.endswith("." + suffix) and host != suffix
    return host == pattern

def scope_decision(url: str, policy: ScopePolicy) -> tuple[bool, str]:
    """Pure decision function. Caller must recheck every redirect destination."""
    try:
        parts = urlsplit(url)
        if parts.username or parts.password or not parts.hostname:
            return False, "invalid_url"
        host = parts.hostname.lower().rstrip(".")
        port = parts.port or {"https": 443, "http": 80}.get(parts.scheme)
        if parts.scheme not in policy.allowed_schemes or port not in policy.allowed_ports:
            return False, "scheme_or_port_denied"
        if any(_host_match(host, x) for x in policy.excluded_hosts):
            return False, "excluded"
        if not any(_host_match(host, x) for x in policy.allowed_hosts):
            return False, "outside_scope"
        return True, "allowed"
    except ValueError:
        return False, "invalid_url"

class KillSwitch:
    def __init__(self):
        self._stopped = threading.Event()
    def stop(self):
        self._stopped.set()
    def reset(self):
        self._stopped.clear()
    def require_running(self):
        if self._stopped.is_set():
            raise RuntimeError("kill_switch_active")

class AuditLog:
    """In-memory append-only hash chain; export and independently anchor the head hash."""
    def __init__(self):
        self.records = []
    def append(self, event: dict):
        prev = self.records[-1]["hash"] if self.records else "0" * 64
        payload = json.dumps({"previous": prev, "event": event}, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        self.records.append({"previous": prev, "event": dict(event), "hash": digest})
    def verify(self):
        prev = "0" * 64
        for record in self.records:
            payload = json.dumps({"previous": prev, "event": record["event"]}, sort_keys=True, separators=(",", ":"))
            if record["previous"] != prev or hashlib.sha256(payload.encode()).hexdigest() != record["hash"]:
                return False
            prev = record["hash"]
        return True

class PassiveImporter:
    """Only evaluates provided URLs; never makes HTTP or DNS requests."""
    def __init__(self, policy: ScopePolicy, kill_switch: KillSwitch, audit: AuditLog):
        self.policy, self.kill_switch, self.audit = policy, kill_switch, audit
    def process(self, urls):
        results = []
        for url in urls:
            self.kill_switch.require_running()
            allowed, reason = scope_decision(url, self.policy)
            self.audit.append({"url": url, "allowed": allowed, "reason": reason})
            results.append((url, allowed, reason))
        return results

# Active validation intentionally NOT implemented. Never treat policy approval as scan approval.
