"""Isolated owner-authenticated approval primitive; not connected to HTTP routes.

Never treat a caller-supplied boolean as proof of owner approval.
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time


def _digest(value):
    if not isinstance(value, str) or len(value) > 512:
        return b""
    return hashlib.sha256(value.encode("utf-8")).digest()


def _fingerprint(route, operation, arguments, request_id):
    if not all(isinstance(x, str) and 1 <= len(x) <= 128 and x.isprintable()
               for x in (route, operation, request_id)):
        raise ValueError("route, operation and request_id required")
    if not route.startswith("/api/selma0/") or not isinstance(arguments, dict):
        raise ValueError("invalid operation scope")
    try:
        data = json.dumps([route, operation, arguments, request_id],
                          sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("invalid approval arguments") from exc
    if len(data) > 131072:
        raise ValueError("approval arguments too large")
    return hashlib.sha256(data).digest()


class ApprovalGate:
    """Proof-backed, short-lived, single-use approvals in a disposable process.

    The owner and approval proofs must originate outside untrusted HTTP content.
    No user-presence attestation or production UI integration is claimed.
    """
    def __init__(self, owner_secret, approval_secret, ttl=30, clock=None):
        if not all(isinstance(s, str) and 32 <= len(s) <= 512
                   for s in (owner_secret, approval_secret)):
            raise ValueError("distinct strong owner and approval proofs required")
        if hmac.compare_digest(owner_secret, approval_secret):
            raise ValueError("distinct proofs required")
        self._owner = _digest(owner_secret)
        self._approval = _digest(approval_secret)
        self.ttl = min(max(int(ttl), 1), 120)
        self._clock = clock or time.monotonic
        self.sessions = {}
        self.approvals = {}
        self._spent = set()
        self._lock = threading.RLock()

    def _purge(self, now):
        for key, expiry in list(self.sessions.items()):
            if now >= expiry:
                self.sessions.pop(key, None)
        for key, record in list(self.approvals.items()):
            if now >= record[2] or record[0] not in self.sessions:
                self.approvals.pop(key, None)
        self._spent = {item for item in self._spent if item[0] in self.sessions}

    def new_session(self, owner_proof):
        if not hmac.compare_digest(_digest(owner_proof), self._owner):
            raise PermissionError("owner proof required")
        with self._lock:
            now = self._clock()
            self._purge(now)
            if len(self.sessions) >= 64:
                raise PermissionError("session capacity reached")
            token = secrets.token_urlsafe(32)
            self.sessions[_digest(token)] = now + 900
            return token

    def _identity(self, token):
        with self._lock:
            self._purge(self._clock())
            digest = _digest(token)
            return digest if digest in self.sessions else None

    def approve(self, token, route, operation, arguments, request_id,
                approval_proof=None, *, trusted_gesture=False):
        # trusted_gesture=True from a caller is deliberately NOT evidence.
        fingerprint = _fingerprint(route, operation, arguments, request_id)
        if not hmac.compare_digest(_digest(approval_proof), self._approval):
            raise PermissionError("independent owner approval proof required")
        with self._lock:
            now = self._clock()
            self._purge(now)
            identity = self._identity(token)
            if identity is None or (identity, request_id) in self._spent:
                raise PermissionError("valid unspent session required")
            if len(self.approvals) >= 256:
                raise PermissionError("approval capacity reached")
            ticket = secrets.token_urlsafe(32)
            self.approvals[_digest(ticket)] = (identity, fingerprint, now + self.ttl, request_id)
            return ticket

    def consume(self, token, ticket, route, operation, arguments, request_id):
        try:
            fingerprint = _fingerprint(route, operation, arguments, request_id)
        except (TypeError, ValueError):
            return False
        with self._lock:
            now = self._clock()
            self._purge(now)
            identity = self._identity(token)
            key = _digest(ticket)
            record = self.approvals.get(key)
            if (identity is None or record is None or record[0] != identity or
                    not hmac.compare_digest(record[1], fingerprint) or
                    now >= record[2] or (identity, request_id) in self._spent):
                return False
            self.approvals.pop(key, None)
            self._spent.add((identity, request_id))
            return True


def private_directory(path):
    if os.path.islink(path):
        raise PermissionError("symlink directory rejected")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def redact_metadata(details):
    """Allowlist metadata: never persist raw free-form arguments or error text."""
    if not isinstance(details, dict):
        return {}
    safe = ("operation", "status", "risk", "decision", "request_id", "event_type")
    return {key: value for key, value in details.items()
            if key in safe and isinstance(value, (str, bool, int))
            and (not isinstance(value, str) or len(value) <= 96)}
