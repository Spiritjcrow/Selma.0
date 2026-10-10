# SELMA0 Authenticated Context Bridge V1

This is a **local, opt-in, authenticated relay boundary** for structured Selma/Gemini/ChatGPT collaboration. It does **not** directly access Gemini conversations, authenticate Google's models, decode speaker identity from voice, call Gemini's API, or auto-export account history. It does not execute external-agent instructions.

## Architecture

```text
Authorized user supplies transcript/summary to local client
        -> exact localhost HTTP POST (127.0.0.1:8765)
        -> HMAC-SHA256 (32-byte random shared key)
        -> timestamp + nonce anti-replay (on-disk, restart-safe)
        -> strict JSON envelope + basic credential guard
        -> transient keyword intent interpretation
        -> existing audited collab.assess registry command
        -> structured status and suggested handoff
```

The main Selma command core remains the only HTTP server. The endpoint is
`POST /api/selma0/bridge/handoff/v1`. It accepts only 8 KiB bodies and requires
HMAC headers (`X-Selma-Time`, `X-Selma-Nonce`, `X-Selma-Signature`). HMAC covers
`POST`, the exact path, timestamp, nonce, and raw request bytes. Clock skew is
limited to 120 seconds; replayed nonces are rejected across process restarts.

### Security properties / limitations

- Requires 64 or more hex digits (at least 32 random bytes) in
  `SELMA0_BRIDGE_HMAC_KEY_V1`. It is disabled without a valid key.
- Key possession authenticates a **local bridge client**, not a person's voice
  or the identity/intent of the Gemini/ChatGPT model. `sender_claim` is a claim.
- Never store/echo original text or secrets; only nonce hashes and Selma's
  existing *metadata-only* audit logs are persisted.
- Basic secret pattern checks reject obvious credentials, but cannot guarantee
  that arbitrary text contains no sensitive information. Only submit text
  you're authorized to share. Never submit recovery phrases or signing keys.
- No outbound network calls, arbitrary command execution, plugin invocation,
  browser extension injections, hidden system-memory exports, or automatic
  changes to configuration or capabilities.
- Keep the listener on loopback. HMAC supplies message integrity/authenticity,
  **not encryption** on an untrusted network. Do not expose this raw endpoint to
  the internet, even via a public tunnel. A separate TLS-authenticated,
  authorization-aware relay is required for cross-device transport.
- Browser `Origin` headers are rejected unless there is an *exact* entry in
  `SELMA0_BRIDGE_ALLOWED_ORIGINS_V1`. Cross-origin preflight/CORS for extensions
  is intentionally not yet enabled; the supplied CLI is the initial client.

### Secure one-time local setup (Termux/Linux)

From the project folder, in a trusted terminal:

```sh
umask 077
mkdir -p "$HOME/.selma0"
[ -f "$HOME/.selma0/bridge-key.hex" ] ||
  python3 -c 'import secrets; print(secrets.token_hex(32))' > "$HOME/.selma0/bridge-key.hex"
chmod 600 "$HOME/.selma0/bridge-key.hex"
export SELMA0_BRIDGE_HMAC_KEY_V1="$(cat "$HOME/.selma0/bridge-key.hex")"
python3 SELMA0_ANDROID_AGENT_V1/selma0_runtime_command_core_android_v1.py
```

For the *client*, load the same key into the second local terminal without
printing it and submit a user-reviewed, non-sensitive summary:

```sh
export SELMA0_BRIDGE_HMAC_KEY_V1="$(cat "$HOME/.selma0/bridge-key.hex")"
printf '%s\n' 'Gemini proposes a versioned API handoff schema for SelmaOS.' |
  python3 SELMA0_ANDROID_AGENT_V1/selma0_bridge_client_v1.py --sender-claim gemini
```

No separate "Gemini API key" is needed for **this local handoff**, because it
does not contact Gemini. Automatic Gemini API messaging still requires an
authorized adapter, provider credentials (kept outside git), explicit scope,
privacy controls, and a properly protected relay transport.

### Envelope format

```json
{
  "protocol": "selma-context-handoff/v1",
  "message_id": "189b816a-8d77-41ae-8fe9-38a44a0f0bee",
  "conversation_id": "0e6b0ad0-1171-4971-bafa-9eec9d0ab139",
  "sender_claim": "gemini",
  "recipient": "selma",
  "text": "Please implement a versioned handoff API.",
  "previous_turns": []
}
```

`text` is used ephemerally by deterministic keyword rules and not passed
through the command router or stored. `previous_turns` is an optional list
of metadata-only entries already accepted by the earlier collaboration schema.
The output contains inferred intent, action kind, topic tags, loop assessment,
and a suggested next action. Intent "confidence" is always **low** until a
validated classifier is integrated. Inferred tasks never authorize actions.

## Reproducible tests

```sh
python3 -m unittest SELMA0_ANDROID_AGENT_V1/tests/test_context_bridge_v1.py -v
python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v
```

Unit tests validate signed/tampered messages, expired timestamps, restart-persistent replay rejection, strict schemas, heuristic intent, speaker uncertainty and policy separation.

## Remaining implementation gates

1. Run repository tests with usable CI, then Android/Termux smoke and localhost integration tests.
2. Add robust source-side consent checks, speech diarization + provenance, and structured turn extraction; distinguish **claimed** from verified speaker identity.
3. Build an optional Gemini API/authorized user-account adapter. Keep provider credentials in private runtime configuration, not GitHub, chat, or voice.
4. Only after explicit network authorization, add TLS with device-specific identities and scoped relay transport for mobile/network-agnostic multi-device use.
5. Threat model the Chrome extension separately, especially permissions, phishing, origin bypasses, and extension message authentication.

## Optional direct Gemini API collaboration

The separate `selma0_gemini_adapter_v1.py` adapter creates a **new** Gemini
API conversation request and relays the generated text to Selma's authenticated
local bridge. It does not recover, sync, or take over existing Gemini app chats,
voice sessions, or hidden model memory. Google documents `generateContent`
over HTTPS with the `x-goog-api-key` header; the model ID defaults to
`gemini-3.8-flash` but can be configured.

This is disabled unless the user configures the Google-issued
`GEMINI_API_KEY`, explicitly enables
`SELMA0_GEMINI_API_ENABLED_V1=1`, and runs a **single** request with
`--authorize-external`. Provider usage may incur charges; review terms and
data handling before transmitting any material. Inputs are never read
automatically from local memory or project files.

```sh
# Only when you intentionally want to send a reviewed message externally:
export SELMA0_BRIDGE_HMAC_KEY_V1="$(cat "$HOME/.selma0/bridge-key.hex")"
export GEMINI_API_KEY="YOUR_KEY_SET_SECURELY_OUTSIDE_VERSION_CONTROL"
export SELMA0_GEMINI_API_ENABLED_V1=1
printf '%s\n' 'Review this SelmaOS bridge schema and recommend one verifiable improvement.' |
  python3 SELMA0_ANDROID_AGENT_V1/selma0_gemini_adapter_v1.py --authorize-external
```

Never paste live secrets into shell commands or commit example credentials.
Prefer a trusted secret manager or a protected session environment for the
provider key, and disable `SELMA0_GEMINI_API_ENABLED_V1` after use.
A real Gemini response/transport still requires runtime credentials, internet,
provider access, and integration smoke evidence.

Test the mock-only provider guard without contacting Google:

```sh
python3 -m unittest SELMA0_ANDROID_AGENT_V1/tests/test_gemini_adapter_v1.py -v
```
