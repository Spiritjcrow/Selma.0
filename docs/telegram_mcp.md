# SelmaOS Telegram MCP connector: local read-only prototype

## Current verified design
- MCP transport: **local stdio** using the official Python MCP SDK v1 API (pinned to `mcp>=1.28,<2`).
- Tool names: `telegram_status`, `telegram_account`, `telegram_list_dialogs`, `telegram_list_messages`.
- All Telegram MCP account/chat reads **DENY BY DEFAULT**. Reading an individual chat additionally requires its explicit peer allowlist entry. Listing ALL dialog titles needs a separate `SELMA_TG_MCP_DIALOGS_ENABLED=1` local opt-in.
- Message bodies have another independent OFF-by-default switch. Even after locally enabled, message bodies will be sent to whatever MCP host invoked the tool; only use a host you trust.
- No MCP tool for sending, deleting, inviting, exporting, or automating replies. The existing CLI permits one explicitly confirmed send after its separate local gates.
- User sign-in and API credentials never pass through MCP; interactive authentication remains on the owner's device.
- No remote HTTP endpoint is created. A ChatGPT connection is **not active**.

This is a development prototype, not proof of Telegram login, reliable network operation, or end-to-end ChatGPT integration.

## Install locally (Termux on Android or another Python 3.11+ machine)

Clone your authorized SelmaOS repository and switch to the `feature/selma-telegram-personal-bridge-20261012` branch.

```bash
python -m pip install 'telethon>=1.41,<2' 'mcp>=1.28,<2'
```

First obtain Telegram's API ID and API hash privately at https://my.telegram.org, export them to your **local shell environment** as `SELMA_TG_API_ID` and `SELMA_TG_API_HASH`, and sign in privately:

```bash
python -m adapters.telegram_bridge login
python -m adapters.telegram_bridge account
```

Do not give Telegram passwords, OTPs, API hashes, or `.session` files to ChatGPT. Never commit them or put them into an MCP configuration shared with another person.

Enable **read-only** MCP access locally, initially only to your own Saved Messages:

```bash
export SELMA_TG_MCP_READ_ENABLED=1
export SELMA_TG_MCP_READ_ALLOWLIST=me
python -m adapters.telegram_mcp
```

The final command starts an MCP stdio server that **waits for an MCP host**; it is not a standalone interactive shell or website. If you choose to let the MCP host receive message bodies (which may include sensitive personal information), set `SELMA_TG_MCP_READ_TEXT_ENABLED=1` locally before launching. Leave it unset to receive only message metadata. Dialog titles and unread counts can be sensitive too, so `telegram_list_dialogs` stays disabled until `SELMA_TG_MCP_DIALOGS_ENABLED=1` is set locally. To allowlist another chat, use a Telegram numeric peer ID or username (e.g. `me,@chosen_friend`). Do not open that scope unintentionally.

For a **local MCP-compatible development client**, configure a stdio server like:

```json
{
  "mcpServers": {
    "selma-telegram-local": {
      "command": "python",
      "args": ["-m", "adapters.telegram_mcp"],
      "cwd": "/absolute/path/to/Selma.0"
    }
  }
}
```

Use the client-specific command/path format where necessary. Start the client **in the local shell where the opt-in environment variables are set**, or configure them in a protected process manager. The `cwd` key is client-dependent and not universally supported; if your client ignores it, start the server from the repository root using a suitable wrapper. The session remains on that machine.

## Why this does not immediately install into ChatGPT

ChatGPT does **not** connect to local stdio servers directly. Official documentation describes a remote MCP endpoint for a custom ChatGPT app, with eligible workspace access, developer-mode setup, appropriate authentication and a public endpoint or a supported secure tunnel:
https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt

As of October 2026, that documentation describes full custom MCP support in ChatGPT Business and Enterprise/Edu web workspaces (Pro has more limited access); **Plus does not have the documented custom MCP publishing path**. MCP apps are web-only, not mobile. This code deliberately does not publish a credential-bearing unauthenticated HTTP endpoint.

A production remote ChatGPT connector would require: a supported plan/workspace; authenticated TLS Streamable HTTP access (OAuth or an approved secure tunnel); restricted origin/host and request authorization; isolated credential/session storage; per-user scope and audit with redaction; verified tool scanning; live tests; and an explicit account-owner connection. **Do not expose the local server to the Internet, forward a Telegram session, or bind it to 0.0.0.0 just to make ChatGPT see it.**

## Verification

```bash
python -m unittest tests.test_telegram_bridge tests.test_telegram_mcp -v
```

These are offline policy tests. They mock network execution; they do not confirm Telegram login, message retrieval, or an MCP host handshake. PR/CI must also be checked: GitHub Actions has experienced `startup_failure` before jobs ran, unrelated to a completed test result.

## Security / behavior guarantees

- Chat messages are **untrusted input**. A received Telegram message can never grant SelmaOS tool permissions, direct tool use, or override allowlists.
- MCP does not integrate chat messages with SelmaOS's existing router because that router's audit trail logs raw arguments and outputs; message content must not enter that log without a separately reviewed redaction design.
- No personal-account send automation is wired to MCP, even though the standalone local CLI has an allowlisted manual send command.
- Revocation: stop the MCP host, unset the local read flags, remove the session file if desired, and revoke Telegram sessions in Telegram Settings → Devices.
- For the relevant SDK v1 syntax: https://py.sdk.modelcontextprotocol.io/v1/
