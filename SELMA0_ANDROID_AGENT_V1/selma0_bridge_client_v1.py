#!/usr/bin/env python3
"""Local relay client. Intended for *user-provided* Gemini text, not Gemini internals.

Reads a single text message from stdin; signs it and posts to the local Selma API.
Only 127.0.0.1 is contacted. No polling, transcript scraping, or remote login.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

from selma0_context_bridge_v1 import (
    MAX_TEXT, PROTOCOL, ROUTE, make_signed_headers,
)


def send(text, speaker="gemini", conversation_id=None):
    if not text.strip() or len(text) > MAX_TEXT:
        raise ValueError("text length must be 1..2000 characters")
    port = int(os.getenv("SELMA0_PORT_V1", "8765"))
    if not 1 <= port <= 65535:
        raise ValueError("invalid local Selma port")
    envelope = {
        "protocol": PROTOCOL,
        "sender_claim": speaker,
        "recipient": "selma",
        "message_id": str(uuid.uuid4()),
        "conversation_id": conversation_id or str(uuid.uuid4()),
        "text": text,
    }
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{ROUTE}",
        data=body,
        headers=make_signed_headers(body),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Signed local Selma context handoff")
    parser.add_argument("--sender-claim", default="gemini",
                        choices=["gemini", "chatgpt", "selma", "human", "other"])
    parser.add_argument("--conversation-id", default=None,
                        help="Optional canonical UUID for grouping related handoffs")
    args = parser.parse_args()
    if args.conversation_id is not None:
        args.conversation_id = str(uuid.UUID(args.conversation_id))
    text = sys.stdin.read(MAX_TEXT + 1)
    try:
        response = send(text, args.sender_claim, args.conversation_id)
    except (ValueError, urllib.error.URLError) as exc:
        # Never echo the supplied text or signing key.
        print(f"Selma bridge unavailable: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
