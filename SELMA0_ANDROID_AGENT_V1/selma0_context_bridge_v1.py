"""Signed local handoffs and conservative intent inference for Selma.0.

HMAC authenticates possession of a locally configured key, NOT Gemini, ChatGPT,
a human speaker, or any underlying model session. Nothing is forwarded online.
This module accepts text transiently; neither text nor secrets are persisted.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from selma0_collaboration_intelligence_v1 import validate_turns

PROTOCOL = "selma-context-handoff/v1"
ROUTE = "/api/selma0/bridge/handoff/v1"
MAX_BODY = 8192
MAX_TEXT = 2000
MAX_SKEW_SECONDS = 120
MAX_PREVIOUS = 32
PERMITTED_FIELDS = frozenset({"protocol", "message_id", "conversation_id", "sender_claim",
                              "recipient", "text", "previous_turns"})
SUPPORTED_SENDERS = frozenset({"gemini", "chatgpt", "selma", "human", "other"})
SECRET_PATTERNS = (
    re.compile(r"(?i)-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|secret|api[_ -]?key|access[_ -]?token|private[_ -]?key)\s*[:=]\s*\S{6,}"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
)
INTENTS = (
    ("security_review", ("bug bounty", "vulnerability", "penetration test", "security finding")),
    ("implementation", ("implement", "build", "write code", "integrate", "create a module", "fix the code")),
    ("handoff", ("transfer", "handoff", "send to selma", "tell chatgpt", "tell gemini")),
    ("comparison", ("compare", "difference between", "which version", "contrast")),
    ("status_review", ("status", "progress", "summary", "what is done")),
)


class BridgeError(ValueError):
    """Safe, non-sensitive protocol error."""


def load_key():
    value = os.getenv("SELMA0_BRIDGE_HMAC_KEY_V1", "").strip()
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise BridgeError("bridge disabled or key invalid") from exc
    if len(key) < 32:
        raise BridgeError("bridge disabled or key invalid")
    return key


def signature(key, timestamp, nonce, raw, method="POST", path=ROUTE):
    prefix = f"{method}\n{path}\n{timestamp}\n{nonce}\n".encode("ascii")
    return hmac.new(key, prefix + raw, hashlib.sha256).hexdigest()


def _str(value, name, limit):
    if not isinstance(value, str) or not 1 <= len(value) <= limit or any(
        ord(c) < 32 and c not in "\n\t" for c in value
    ):
        raise BridgeError(f"invalid {name}")
    return value


def _validate_handoff(raw):
    if not isinstance(raw, dict) or set(raw) - PERMITTED_FIELDS:
        raise BridgeError("unsupported handoff schema")
    if raw.get("protocol") != PROTOCOL or raw.get("recipient") != "selma":
        raise BridgeError("unsupported protocol or recipient")
    for k in ("message_id", "conversation_id"):
        try:
            if str(uuid.UUID(_str(raw.get(k), k, 64))) != raw[k]:
                raise ValueError()
        except (ValueError, AttributeError) as exc:
            raise BridgeError(f"invalid {k}") from exc
    sender = raw.get("sender_claim")
    if sender not in SUPPORTED_SENDERS:
        raise BridgeError("sender_claim not supported")
    body = _str(raw.get("text"), "text", MAX_TEXT).strip()
    if not body:
        raise BridgeError("empty text")
    if any(pattern.search(body) for pattern in SECRET_PATTERNS):
        raise BridgeError("possible credential in text; handoff refused")
    previous = raw.get("previous_turns", [])
    if not isinstance(previous, list) or len(previous) > MAX_PREVIOUS:
        raise BridgeError("invalid previous_turns")
    if previous:
        try:
            previous = validate_turns(previous)
        except ValueError as exc:
            raise BridgeError("invalid prior metadata (no transcripts allowed)") from exc
    return sender, body, previous


def infer_context(text):
    """Bounded heuristics only: do not represent them as semantic certainty."""
    lowered = text.lower()
    matched = [intent for intent, words in INTENTS if any(w in lowered for w in words)]
    intent = matched[0] if matched else "undetermined"
    if intent == "handoff":
        action = "handoff"
    elif intent in {"implementation", "security_review"}:
        action = "propose"
    elif "?" in text or re.search(r"(?i)\b(?:can you|could you|please|would you)\b", text):
        action = "ask"
    elif re.fullmatch(r"(?i)[\s.!]*(?:thanks|thank you|okay|ok|understood|agreed)[\s.!]*", text):
        action = "ack"
    else:
        action = "propose"
    tags = [name for name, pattern in (
        ("selma", r"\bselma(?:os|\.0)?\b"),
        ("bug_bounty", r"\bbug bounty|\bwrangler\b"),
        ("audio", r"\baudio|\bspeech|\bvoice\b"),
        ("api", r"\bapi|\brouter|\bendpoint\b"),
    ) if re.search(pattern, lowered)]
    return {"intent": intent, "action_kind": action, "topic_tags": tags,
            "method": "offline_keyword_heuristic",
            "confidence": "low", "executes_instructions": False}


class ReplayLedger:
    """Durable replay prevention, surviving process restart. No message text stored."""

    def __init__(self, directory=None, clock=None):
        self.root = Path(directory or os.getenv("SELMA0_BRIDGE_DATA_DIR_V1",
                                               "~/.selma0/bridge_v1")).expanduser()
        self.path = self.root / "nonces.sqlite3"
        self.clock = clock or time.time
        self.lock = threading.RLock()

    def check_and_consume(self, nonce, when):
        with self.lock:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(self.root, 0o700)
            if not self.path.exists():
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            os.chmod(self.path, 0o600)
            digest = hashlib.sha256(nonce.encode("ascii")).hexdigest()
            with sqlite3.connect(self.path, timeout=3) as con:
                con.execute("CREATE TABLE IF NOT EXISTS used_nonce (digest TEXT PRIMARY KEY, expires INTEGER NOT NULL)")
                # Avoid pruning within the whole replay-validity interval.
                con.execute("DELETE FROM used_nonce WHERE expires < ?", (int(self.clock()),))
                try:
                    con.execute("INSERT INTO used_nonce VALUES (?,?)",
                                (digest, when + MAX_SKEW_SECONDS + 1))
                except sqlite3.IntegrityError as exc:
                    raise BridgeError("replayed request") from exc


class LocalHandoffBridge:
    def __init__(self, ledger=None, clock=None):
        self.clock = clock or time.time
        self.ledger = ledger or ReplayLedger(clock=self.clock)

    def verify(self, headers, raw, method="POST", path=ROUTE):
        key = load_key()
        if method != "POST" or path != ROUTE:
            raise BridgeError("unsupported route")
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BODY:
            raise BridgeError("invalid request size")
        ts = str(headers.get("X-Selma-Time", ""))
        nonce = str(headers.get("X-Selma-Nonce", ""))
        mac = str(headers.get("X-Selma-Signature", "")).lower()
        if not re.fullmatch(r"[0-9]{10,11}", ts) or not re.fullmatch(r"[a-f0-9]{32,64}", nonce):
            raise BridgeError("invalid authentication headers")
        if not re.fullmatch(r"[a-f0-9]{64}", mac):
            raise BridgeError("invalid signature")
        now = int(self.clock())
        if abs(now - int(ts)) > MAX_SKEW_SECONDS:
            raise BridgeError("request expired or clock out of sync")
        expected = signature(key, ts, nonce, raw, method, path)
        if not hmac.compare_digest(expected, mac):
            raise BridgeError("signature verification failed")
        self.ledger.check_and_consume(nonce, int(ts))
        return True

    def process(self, raw, evaluator):
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError("invalid JSON document") from exc
        sender, text, previous = _validate_handoff(data)
        context = infer_context(text)
        # Transport peer is authenticated, but model/speaker identity is not.
        new_turn = {"speaker_id": sender, "speaker_confidence": 0.0,
                    "action_kind": context["action_kind"], "artifact_produced": False,
                    "evidence": "none", "source_kind": "import"}
        turns = (previous + [new_turn])[-32:]
        validated = validate_turns(turns)
        assessment = evaluator(validated)
        return {"protocol": PROTOCOL, "message_id": data["message_id"],
                "conversation_id": data["conversation_id"], "sender_claim": sender,
                "authentication": "shared_key_client_only_not_model_or_voice_identity",
                "context": context, "assessment": assessment,
                "text_stored": False, "external_forwarding": False}


def make_signed_headers(raw, key=None, timestamp=None, nonce=None):
    """Local CLI/testing helper. Never put a key or its signature in logs."""
    key = load_key() if key is None else key
    ts = str(int(time.time()) if timestamp is None else int(timestamp))
    nonce = nonce or secrets.token_hex(24)
    return {"Content-Type": "application/json",
            "X-Selma-Time": ts, "X-Selma-Nonce": nonce,
            "X-Selma-Signature": signature(key, ts, nonce, raw)}
