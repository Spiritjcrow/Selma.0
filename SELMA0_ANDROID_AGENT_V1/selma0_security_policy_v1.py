"""Isolated security primitives. Not wired to production HTTP routes yet."""
import hashlib
import hmac
import json
import os
import secrets
import time

class ApprovalGate:
    def __init__(self, ttl=45):
        self.ttl = min(max(int(ttl), 1), 120)
        self.sessions = {}
        self._owner_proof = secrets.token_urlsafe(32)
        self.approvals = {}

    def new_session(self, owner_proof=None):
        if not hmac.compare_digest(str(owner_proof), self._owner_proof):
            raise PermissionError('owner pairing required')
        token = secrets.token_urlsafe(32)
        self.sessions[hashlib.sha256(token.encode()).digest()] = time.monotonic() + 900
        return token

    def _identity(self, token):
        digest = hashlib.sha256(str(token).encode()).digest()
        for known, expiry in list(self.sessions.items()):
            if hmac.compare_digest(digest, known) and time.monotonic() < expiry:
                return known
        return None

    def approve(self, token, operation, arguments, owner_proof=None):
        identity = self._identity(token)
        if identity is None or not hmac.compare_digest(str(owner_proof), self._owner_proof):
            raise PermissionError("trusted local approval required")
        ticket = secrets.token_urlsafe(32)
        payload = json.dumps([operation, arguments], sort_keys=True, separators=(",", ":"))
        self.approvals[hashlib.sha256(ticket.encode()).digest()] = (
            identity, hashlib.sha256(payload.encode()).digest(), time.monotonic() + self.ttl
        )
        return ticket

    def consume(self, token, ticket, operation, arguments):
        identity = self._identity(token)
        key = hashlib.sha256(str(ticket).encode()).digest()
        record = self.approvals.pop(key, None)
        if identity is None or record is None:
            return False
        payload = json.dumps([operation, arguments], sort_keys=True, separators=(",", ":"))
        return (hmac.compare_digest(identity, record[0])
                and hmac.compare_digest(hashlib.sha256(payload.encode()).digest(), record[1])
                and time.monotonic() < record[2])

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
