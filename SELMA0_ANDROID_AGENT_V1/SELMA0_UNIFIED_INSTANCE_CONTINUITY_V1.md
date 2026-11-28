# Selma° unified logical-instance continuity V1

**Development status:** Source-only integration on feature branch; no live voice,
device, full regression, or CI verification established.

## Contract

Text chat and voice **transcripts** are input modalities to the same
`Selma0RuntimeAndroidV1.chat(message, modality)` call. They share one local
SQLite identity (`identity_id`), logical conversation (`thread_id`),
context generation, mandatory empathy guidance, and persisted event archive.
The `modality` parameter is `text` or `voice`. Speech recognition and speech
synthesis adapters must submit recognized text to this API, and are **not
implemented by this change**.

### Existing approved HTTP entry point

```http
POST /api/selma0/chat/v1
Content-Type: application/json
```

```json
{"message":"Can you continue from the previous text turn?","modality":"voice","confirmed":true,"request_id":"unique-per-turn"}
```

The command-core endpoint continues to require approval for write-class
`selma.chat`, and retains its audit and replay/idempotency mechanism.
Use a unique request ID for each distinct turn and the same ID when retrying
a turn. Only authenticated and authorized callers should be able to access
a remote instance. Existing loopback host/origin checks do **not** establish
full user authentication.

### Durable state

`GET /api/selma0/status/v1` includes the logical
`identity_id`, `thread_id`, `context_generation`, pinned model route and
configuration fingerprint. No API token is written to these fields. On
restart, the same database retains the identity, thread, lock, and archive.

New conversation events are labeled with identity, thread, generation and
modality. Legacy events without these labels are visible only in generation
zero for backwards compatibility. A bounded recent-history window is sent
to the model; the full archive is **not** sent on every inference call.

### Provider continuity

The initial successful reply selects the local model or, if local inference
fails, the configured online fallback. That route's endpoint and model name
are fingerprinted and pinned in SQLite. Later turns use only the selected
route. If that model is unavailable or its configured endpoint/model changes,
Selma returns an unavailable/error response instead of silently switching
the underlying provider. Note that an external provider can change its
model implementation behind an unchanged public model identifier; this V1
cannot cryptographically guarantee identical model weights or exact
behavior across remote provider updates.

### Controlled refresh

`selma.context.refresh` is a **write-class command requiring existing
approval** via `POST /api/selma0/tools/execute/v1`. It increments context
generation and releases the provider lock but keeps the same stable identity,
same thread ID, and full archived history. It is not a delete/reset and
must not be called as an automatic response to errors or mood inference.

```json
{"tool":"selma.context.refresh","arguments":{},"approved":true,"request_id":"unique-refresh-id"}
```

### Current limitations

- Voice is transcript-only until real ASR/TTS and microphone permission
  flows use this endpoint and are tested.
- Logical identity is stable in a persistent database, but the underlying
  Python server and model inference processes can restart. Do not call this
  an everlasting model process or conscious identity.
- A single in-process turn lock and SQLite connection lock serialize
  ordinary concurrent requests. Multi-process locking, independent device
  replication, reconnect/session-token authentication, causal event IDs,
  full multi-turn atomic transaction recovery and failover require further
  engineering.
- The event archive persists, but the model sees only the bounded context
  window. Retrieval/summarization and durable cross-device sync are separate.
- This branch includes unmerged empathy PR #132 as its dependency. Do not
  merge ahead of that branch without resolving review and test gates.
- CI previously showed failed jobs without steps; no CI green, production
  deployment or physical Android validation is claimed.

## Verification required before release

```bash
python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v
```

Require actual runtime tests for text→voice→text, restart, device voice,
permission denial, repeated HTTP request IDs, provider outage, bad modality,
context refresh approval, concurrency and crash recovery. Record exact test
results and commit hashes in the master execution ledger.
