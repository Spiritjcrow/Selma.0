"""Local, read-only Telegram user session for SelmaOS.

No bot token, chat writes, forwarding, or model-command dispatch is supported.
Run only on a device owned and controlled by the account holder.
Requires Telethon 1.x: python -m pip install 'telethon>=1.40,<2'
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import stat
from pathlib import Path


def session_base() -> Path:
    """Return a private local directory, never a synced project checkout."""
    root = Path.home() / ".local" / "share" / "selma0" / "telegram"
    if root.is_symlink():
        raise RuntimeError("Refusing a symlinked Telegram session directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    base = root / "somagram_user_v1"
    session_file = base.with_suffix(".session")
    if session_file.is_symlink():
        raise RuntimeError("Refusing a symlinked Telegram session")
    if session_file.exists() and stat.S_IMODE(session_file.stat().st_mode) & 0o077:
        raise RuntimeError("Session permissions too broad; chmod 600 the .session file")
    return base


def credentials() -> tuple[int, str]:
    raw_id = os.environ.get("SELMA0_TELEGRAM_API_ID_V1") or input(
        "Telegram application API ID: "
    ).strip()
    if not raw_id.isdecimal() or int(raw_id) < 1:
        raise ValueError("API ID must be a positive number")
    api_hash = os.environ.get("SELMA0_TELEGRAM_API_HASH_V1") or getpass.getpass(
        "Telegram application API hash (hidden): "
    )
    if not api_hash or not api_hash.strip():
        raise ValueError("API hash must not be empty")
    return int(raw_id), api_hash.strip()


async def perform(action: str, limit: int = 5) -> int:
    """Only inspect the account. Login may create one local session."""
    from telethon import TelegramClient

    if action not in {"login", "status", "dialogs"}:
        raise ValueError("Unsupported read-only operation")
    api_id, api_hash = credentials()
    base = session_base()
    client = TelegramClient(
        str(base), api_id, api_hash, receive_updates=False
    )
    try:
        if action == "login":
            # Prompts locally for phone, login code, and 2FA when required.
            await client.start()
        else:
            await client.connect()
            if not await client.is_user_authorized():
                print("Not authorized yet. Run the login command locally.")
                return 2

        me = await client.get_me()
        if me is None:
            print("Telegram account identity unavailable.")
            return 2
        name = ("@" + me.username) if getattr(me, "username", None) else "(no username)"
        print(f"Telegram session verified: {name}, user ID {me.id}")
        if action == "dialogs":
            # Only explicit invocation reads dialog titles. No messages read.
            dialogs = await client.get_dialogs(limit=limit)
            for i, dialog in enumerate(dialogs, 1):
                print(f"{i}. {dialog.title}")
            print(f"Listed {len(dialogs)} dialog titles locally (no messages).")
        return 0
    finally:
        await client.disconnect()
        session_file = base.with_suffix(".session")
        if session_file.exists() and not session_file.is_symlink():
            session_file.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Somagram Telegram user login and read-only verification"
    )
    parser.add_argument("action", choices=("login", "status", "dialogs"))
    parser.add_argument("--limit", type=int, default=5, help="dialogs: 1-20")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    os.umask(0o077)
    try:
        return asyncio.run(perform(args.action, args.limit))
    except (KeyboardInterrupt, EOFError):
        print("Cancelled. No Telegram chat changes were made.")
        return 130
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Setup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
