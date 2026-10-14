"""Staged, standalone owner/session/approval primitives for issue #43.

Not an HTTP integration. A trusted UI must collect owner and per-operation
approval secrets out of band. Neither a JSON boolean nor an HTTP Origin header
establishes user presence. No secrets are logged or persisted here.
"""
import hashlib
import hmac
import json
import secrets
import threading
import time


def _digest(value):
    if not isinstance(value, str) or len(value) > 512:
        return b""
    return hashlib.sha256(value.encode("utf-8")).digest()


def _fingerprint(operation, arguments, request_id):
    if (not isinstance(operation, str) or not (1 <= len(operation) <= 128)
            or not operation.isprintable() or operation != operation.strip()):
        raise ValueError("operation required")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    if (not isinstance(request_id, str) or not (1 <= len(request_id) <= 128)
            or not request_id.isprintable() or request_id != request_id.strip()):
        raise ValueError("request_id required")
    try:
        encoded = json.dumps([operation, arguments, request_id], sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        payload = encoded.encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ValueError("approval arguments must be bounded JSON") from exc
    if len(payload) > 131072:
        raise ValueError("approval arguments too large")
    return hashlib.sha256(payload).digest()


def exact_loopback_origin(origin, host, port):
    """Exact browser origin check, independent of authenticated identity."""
    if not isinstance(origin, str) or not origin or origin.strip() != origin:
        return False
    if host not in ("127.0.0.1", "::1", "localhost"):
        return False
    authority = f"[{host}]" if ":" in host else host
    return origin == f"http://{authority}:{port}"


class OwnerApprovalAuthority:
    """In-memory single-owner authority; pair and approve only with separate proofs."""
    def __init__(self, owner_secret, approval_secret, *, session_ttl=900,
                 approval_ttl=30, clock=None, max_sessions=64,
                 max_tickets=256, max_spent=4096):
        if (not isinstance(owner_secret, str) or not (32 <= len(owner_secret) <= 512) or
                not isinstance(approval_secret, str) or not (32 <= len(approval_secret) <= 512) or
                hmac.compare_digest(owner_secret, approval_secret)):
            raise ValueError("distinct strong owner and approval secrets required")
        self._owner_hash = _digest(owner_secret)
        self._approval_hash = _digest(approval_secret)
        self._clock = clock or time.monotonic
        self._session_ttl = min(max(int(session_ttl), 1), 900)
        self._approval_ttl = min(max(int(approval_ttl), 1), 120)
        self._max_sessions = min(max(int(max_sessions), 1), 1024)
        self._max_tickets = min(max(int(max_tickets), 1), 8192)
        self._max_spent = min(max(int(max_spent), 1), 65536)
        self._sessions = {}
        self._tickets = {}
        self._spent = {}
        self._lock = threading.RLock()

    def _purge(self, now):
        for key, record in list(self._sessions.items()):
            if record[1] <= now:
                self._sessions.pop(key, None)
        for key, record in list(self._tickets.items()):
            if record[2] <= now:
                self._tickets.pop(key, None)
        for key, expiry in list(self._spent.items()):
            if expiry <= now:
                self._spent.pop(key, None)

    def pair(self, owner_proof, client_label):
        if (not isinstance(client_label, str) or
                not (1 <= len(client_label) <= 64) or
                not client_label.isprintable()):
            raise ValueError("valid client label required")
        if not hmac.compare_digest(_digest(owner_proof), self._owner_hash):
            raise PermissionError("owner proof required")
        with self._lock:
            now = self._clock()
            self._purge(now)
            if len(self._sessions) >= self._max_sessions:
                raise PermissionError("session capacity reached")
            token = secrets.token_urlsafe(32)
            self._sessions[_digest(token)] = (client_label, now + self._session_ttl)
            return token

    def identity(self, session_token):
        with self._lock:
            now = self._clock()
            self._purge(now)
            record = self._sessions.get(_digest(session_token))
            return record[0] if record is not None else None

    def issue(self, session_token, approval_proof, operation, arguments, request_id):
        fingerprint = _fingerprint(operation, arguments, request_id)
        if not hmac.compare_digest(_digest(approval_proof), self._approval_hash):
            raise PermissionError("per-operation owner approval required")
        with self._lock:
            now = self._clock()
            self._purge(now)
            identity = _digest(session_token)
            if identity not in self._sessions:
                raise PermissionError("authenticated session required")
            if (identity, request_id) in self._spent:
                raise PermissionError("request already consumed")
            if len(self._tickets) >= self._max_tickets or len(self._spent) >= self._max_spent:
                raise PermissionError("approval capacity reached")
            ticket = secrets.token_urlsafe(32)
            self._tickets[_digest(ticket)] = (identity, fingerprint,
                                             now + self._approval_ttl)
            return ticket

    def consume(self, session_token, ticket, operation, arguments, request_id):
        try:
            fingerprint = _fingerprint(operation, arguments, request_id)
        except (TypeError, ValueError):
            return False
        with self._lock:
            now = self._clock()
            self._purge(now)
            identity = _digest(session_token)
            record = self._tickets.get(_digest(ticket))
            valid = (identity in self._sessions and record is not None and
                     hmac.compare_digest(identity, record[0]) and
                     hmac.compare_digest(fingerprint, record[1]) and
                     now < record[2] and
                     (identity, request_id) not in self._spent and
                     len(self._spent) < self._max_spent)
            if valid:
                self._tickets.pop(_digest(ticket), None)
                self._spent[(identity, request_id)] = self._sessions[identity][1]
            return valid

    def revoke(self, session_token):
        with self._lock:
            identity = _digest(session_token)
            self._sessions.pop(identity, None)
            for key in list(self._spent):
                if hmac.compare_digest(identity, key[0]):
                    self._spent.pop(key, None)
            for key, record in list(self._tickets.items()):
                if hmac.compare_digest(identity, record[0]):
                    self._tickets.pop(key, None)
