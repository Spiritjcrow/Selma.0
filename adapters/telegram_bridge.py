"""Opt-in, device-local Telegram personal-account bridge for SelmaOS.

Telethon is an OPTIONAL runtime dependency. This module never authenticates
on behalf of a user in ChatGPT and does not expose credentials to the web API.
It deliberately avoids the existing command router for message content:
the router currently audits raw inputs and outputs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_MESSAGE_CHARS = 2000
MAX_RESULTS = 50


class TelegramBridgeError(RuntimeError):
    """Safe, user-facing refusal or setup error."""


def _yes(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _session_dir() -> Path:
    base = os.environ.get("SELMA_TG_SESSION_DIR", "").strip()
    return Path(base).expanduser() if base else Path.home() / ".local" / "share" / "selma" / "telegram"


def _session_base() -> Path:
    return _session_dir() / "selma_personal"


def _session_file() -> Path:
    return Path(str(_session_base()) + ".session")


def _credentials() -> tuple[int, str]:
    api_id = os.environ.get("SELMA_TG_API_ID", "").strip()
    api_hash = os.environ.get("SELMA_TG_API_HASH", "").strip()
    if not api_id.isdecimal() or int(api_id) <= 0:
        raise TelegramBridgeError("Set SELMA_TG_API_ID from https://my.telegram.org")
    if not re.fullmatch(r"[A-Fa-f0-9]{32}", api_hash):
        raise TelegramBridgeError("Set SELMA_TG_API_HASH locally (never put it in GitHub or chat)")
    return int(api_id), api_hash


def status() -> dict[str, object]:
    """Safe to register in SelmaOS's existing audited tool router."""
    has_id = os.environ.get("SELMA_TG_API_ID", "").strip().isdecimal()
    has_hash = bool(re.fullmatch(r"[A-Fa-f0-9]{32}", os.environ.get("SELMA_TG_API_HASH", "").strip()))
    return {
        "adapter": "telegram_personal_v1",
        "credentials_configured": bool(has_id and has_hash),
        "local_session_present": _session_file().is_file(),
        "telegram_authorization_verified": False,  # status is entirely offline
        "send_enabled": _yes("SELMA_TG_SEND_ENABLED"),
        "live_chatgpt_connector": False,
    }


def _allowed_peers() -> set[str]:
    # Self-chat only unless the local operator explicitly adds destinations.
    raw = os.environ.get("SELMA_TG_SEND_ALLOWLIST", "me")
    return {item.strip().lower().lstrip("@") for item in raw.split(",") if item.strip()}


def ensure_send_allowed(peer: str, text: str, *, confirmed: bool) -> None:
    destination = peer.strip().lower().lstrip("@")
    if not destination or destination not in _allowed_peers():
        raise TelegramBridgeError("Destination is not in SELMA_TG_SEND_ALLOWLIST")
    if not text.strip() or len(text) > MAX_MESSAGE_CHARS:
        raise TelegramBridgeError("Message must contain 1 to 2000 characters")
    if not _yes("SELMA_TG_SEND_ENABLED"):
        raise TelegramBridgeError("Sending is disabled; set SELMA_TG_SEND_ENABLED=1 locally")
    if confirmed is not True:
        raise TelegramBridgeError("This send needs an explicit --confirm-send")


def _ensure_private_dir() -> None:
    root = _session_dir()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise TelegramBridgeError("Session directory must not be a symlink")
    if os.name == "posix":
        root.chmod(0o700)


def _secure_session_file() -> None:
    session_file = _session_file()
    if os.name == "posix" and session_file.exists():
        session_file.chmod(0o600)


def _emit(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def _client():
    try:
        from telethon.sync import TelegramClient
    except ImportError as exc:
        raise TelegramBridgeError("Install the optional library: python -m pip install 'telethon>=1.41,<2'") from exc
    api_id, api_hash = _credentials()
    _ensure_private_dir()
    return TelegramClient(str(_session_base()), api_id, api_hash)


def _login() -> int:
    # Authentication happens interactively in the local terminal, NEVER in ChatGPT.
    client = _client()
    try:
        client.start()
        me = client.get_me()
        _emit({"authenticated": True, "user_id": me.id, "username": me.username})
        return 0
    finally:
        client.disconnect()
        _secure_session_file()


def _authorized_client():
    if not _session_file().is_file():
        raise TelegramBridgeError("No local Telegram session; run 'login' on your device")
    client = _client()
    client.connect()
    if not client.is_user_authorized():
        client.disconnect()
        raise TelegramBridgeError("Telegram session expired; run 'login' on your device")
    _secure_session_file()
    return client


def _read(client, args) -> int:
    if args.command == "account":
        me = client.get_me()
        _emit({"authorized": True, "user_id": me.id, "username": me.username})
    elif args.command == "dialogs":
        dialogs = client.get_dialogs(limit=args.limit)
        _emit({"dialogs": [{"id": d.id, "title": d.name, "unread_count": d.unread_count} for d in dialogs]})
    elif args.command == "messages":
        messages = client.get_messages(args.peer, limit=args.limit)
        _emit({"peer": args.peer, "messages": [
            {"id": m.id, "date": m.date.isoformat() if m.date else None,
             "outgoing": bool(m.out),
             **({"text": (m.message or "")[:1000]} if args.show_text else {})}
            for m in messages
        ]})
    return 0


def _send(client, args) -> int:
    ensure_send_allowed(args.peer, args.text, confirmed=args.confirm_send)
    result = client.send_message(args.peer, args.text)
    _emit({"sent": True, "peer": args.peer, "message_id": result.id})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SelmaOS local Telegram account bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Offline setup status (does not verify Telegram authorization)")
    sub.add_parser("login", help="Interactive local-only Telegram login")
    sub.add_parser("account", help="Check Telegram authorization")
    dialogs = sub.add_parser("dialogs", help="List chats locally")
    dialogs.add_argument("--limit", type=int, default=15)
    messages = sub.add_parser("messages", help="Read recent messages locally")
    messages.add_argument("--peer", required=True)
    messages.add_argument("--limit", type=int, default=10)
    messages.add_argument("--show-text", action="store_true", help="Print message bodies to the local terminal")
    send = sub.add_parser("send", help="Send ONE message; locked behind local opt-in and confirmation")
    send.add_argument("--peer", required=True)
    send.add_argument("--text", required=True)
    send.add_argument("--confirm-send", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            _emit(status())
            return 0
        if args.command in {"dialogs", "messages"} and not 1 <= args.limit <= MAX_RESULTS:
            raise TelegramBridgeError("Limit must be between 1 and 50")
        if args.command == "send":
            # Deny before making ANY Telegram connection.
            ensure_send_allowed(args.peer, args.text, confirmed=args.confirm_send)
        if args.command == "login":
            return _login()
        client = _authorized_client()
        try:
            return _send(client, args) if args.command == "send" else _read(client, args)
        finally:
            client.disconnect()
    except (TelegramBridgeError, OSError) as exc:
        print("Telegram bridge: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
