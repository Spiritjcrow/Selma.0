# SelmaOS Telegram personal-account bridge (experimental)

**Truth state:** The code exists in SelmaOS, but no Telegram account has been authenticated or controlled by ChatGPT. Telegram has no native ChatGPT plugin available in this session. This is an **independent, local MTProto client**, NOT a ChatGPT connector or a deployed bot.

## Scope

- Local, interactive sign-in to a personal Telegram account using Telethon 1.x.
- Account authorization check; list dialogs; list recent message metadata; optional local-only text output.
- One-message send command. **Disabled by default**, destination-allowlisted, and additionally requires a per-command confirmation flag.
- Offline `status()` function intended for SelmaOS's existing command-tool registry.
- No scraping, bulk messaging, auto-replies, secret/chat export, remote HTTP API, or unattended account sign-in.
- Telegram **Secret Chats** are not accessible using this Telethon cloud-chat adapter.
- The existing Selma command router logs tool inputs and outputs. **Never route Telegram message bodies or API secrets through that logger.** The bridge intentionally exposes *status only* through the router.

## Setup on your OWN Android/Termux, Linux or Codespaces terminal

1. Go to [my.telegram.org](https://my.telegram.org) while logged in to your Telegram account. Choose **API development tools**, register an app, and obtain an API ID and API hash. Telegram requires these for user-client APIs.
2. From the repository root, install the optional library:

   ```bash
   python -m pip install 'telethon>=1.41,<2'
   ```

3. Set `SELMA_TG_API_ID` and `SELMA_TG_API_HASH` in your **local shell environment only**, using the actual values from Telegram. Never enter the API hash, login codes, 2FA password, bot tokens or session files in ChatGPT, an issue, a commit or a pull request. Prefer a protected private secrets file outside the repository over putting credentials in command history.
4. From the repository root, run the interactive login command **on your own device**:

   ```bash
   python -m adapters.telegram_bridge login
   ```

   Telethon prompts locally for account phone/code/password if needed. Selma/ChatGPT cannot complete this authentication remotely.

5. Check and use read operations:

   ```bash
   python -m adapters.telegram_bridge status
   python -m adapters.telegram_bridge account
   python -m adapters.telegram_bridge dialogs --limit 10
   python -m adapters.telegram_bridge messages --peer me --limit 5
   python -m adapters.telegram_bridge messages --peer me --limit 5 --show-text
   ```

The session database stays under `~/.local/share/selma/telegram/` unless you set `SELMA_TG_SESSION_DIR`. On POSIX systems, its folder is chmod 700 and the `.session` database is chmod 600 after use. Protect that file as you would a password: possession of a Telethon session file can grant account access. Do not synchronize or commit it. Revoke unwanted sessions inside an official Telegram client.

## Explicit sending, OFF by default

To enable one user-chosen destination, first set these **locally**:

```bash
export SELMA_TG_SEND_ENABLED=1
export SELMA_TG_SEND_ALLOWLIST=me
python -m adapters.telegram_bridge send --peer me --text 'SelmaOS connection test' --confirm-send
```

No send occurs without every gate: installed dependency, Telegram-authenticated device session, global sending flag, exact allowlisted destination, and the specific `--confirm-send` flag. The default allowlist is **me** (Saved Messages) only. The bridge has no bulk-send interface.

## SelmaOS command router

The existing SelmaOS command-tool API registers `telegram.status` as a low-risk **offline** status check. It reports whether the local environment and session file exist, not whether ChatGPT has access or whether Telegram has verified authorization. Private chat text is deliberately not registered with the current router because the router stores raw arguments/results in its audit log.

## Validation

```bash
python -m unittest tests.test_telegram_bridge -v
```

The tests are local, network-free policy tests; they **do not verify live Telegram sign-in, Android compatibility, or delivery**. Live verification requires the real account owner to sign in privately on a device and opt in to a self-chat test.

## Security and platform limitations

- Telegram forbids performing actions without user knowledge/consent and abuse like spamming. Official terms: https://core.telegram.org/api/terms and https://core.telegram.org/api/obtaining_api_id
- Do not use Telegram information for training/fine-tuning AI or unauthorized scraping. This prototype does not send message contents to any model.
- This adapter is **not** automatically connected to the ChatGPT Telegram account or available as a remote GPT plugin. A future authenticated, privacy-reviewed connector is separate work.
- Stop access by removing the local session file and revoking the session in Telegram's Settings > Devices. Unset environment variables to disable credentials/sends.

