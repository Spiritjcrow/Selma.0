# Somagram: Telegram account login (read-only V1)

**Status:** candidate implementation, not yet deployed or validated against a live Telegram account. No ChatGPT-to-Telegram account connection exists automatically.

The existing **Selma Bot** is controlled by Telegram's Bot API token. It is separate from the **user account** application API ID and API hash obtained from my.telegram.org. The user-account session can inspect the owner's Telegram account, while a bot cannot automatically read the owner's private chats.

## Safety boundary

- The initial tool permits only `login`, `status`, and `dialogs --limit 1..20` (dialog titles only).
- It does not fetch messages, send or delete messages, forward content, manage contacts, access groups, issue device commands, or execute model-generated instructions.
- No browser/cloud ChatGPT connection is created. Login prompts run **only on the owner's Android/Termux device**.
- Session files are reusable account credentials. The `.session` file lives under `~/.local/share/selma0/telegram/` (private mode) and must **never** be shared, backed up to cloud folders, pasted into chat, or committed to Git.
- Use only credentials for a Telegram account you control. Login codes and 2FA passwords must remain on your device.

## Android / Termux trial

On the device that owns the account, install Termux from its trusted distribution channel. In a repository checkout containing this file:

```sh
pkg install -y python git
python -m pip install 'telethon>=1.40,<2'
cd SELMA0_ANDROID_AGENT_V1
python selma0_telegram_account_readonly_v1.py login
python selma0_telegram_account_readonly_v1.py status
python selma0_telegram_account_readonly_v1.py dialogs --limit 5
```

During `login`, enter the **application API ID** (numeric), **application API hash**, phone number, Telegram login code, and two-step password if requested. The local prompt for API hash is hidden. Avoid storing secrets in shell history or a synced Drive screenshot.

If starting from the existing SelmaOS bootstrap rather than the repository checkout, install or refresh the V1 bootstrap first, so the new script is copied into `~/SELMA0_ANDROID_AGENT_V1/`.

The bot token you saved is **not** used in this user-account step. Do not enter the bot token in the API hash prompt.

## Offline verification

```sh
python -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_telegram_account_readonly_v1.py' -v
```

This uses a fake Telegram client, needs no actual API keys or network access, and proves the read-only method boundary. Real account login needs Telegram network access.

## Future reviewed integration

After local login verification, design a separate permission-checked, audited integration with SelmaOS's existing command-control plane. Enabling message reads, sending, archiving, forwarding, and account-management actions must be implemented and reviewed as separate capabilities. The current V1 tool cannot perform them.
