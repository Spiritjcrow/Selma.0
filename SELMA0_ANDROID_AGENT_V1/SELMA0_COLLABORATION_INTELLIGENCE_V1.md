# SELMA0 Collaboration Intelligence V1

A deterministic, offline-first **metadata evaluator**, not a conscious agent, speaker-recognition model, voice listener, or connection to Gemini. The component detects stalled acknowledgements/handoffs, ambiguously attributed speakers, unverified delivery, and no-evidence progress. Its adaptive policy only **suggests** bounded threshold changes after at least three distinct labeled observations. Suggestions do not self-activate.

## Data contract (no raw transcripts)

Pass a `turns` list of 1–64 structured metadata objects with:

- `speaker_id`: explicit bridge label such as `user`, `gemini`, or `chatgpt` (not voice verification)
- `speaker_confidence`: upstream estimate 0.0–1.0, not calculated here
- `action_kind`: `ack`, `ask`, `propose`, `handoff`, `deliver`, `verify`, `block`
- `artifact_produced`: boolean, caller-reported, not self-proving
- `evidence`: `none`, `claim`, `test`, `external_verified` (caller-reported)
- `source_kind`: `voice_transcript`, `human`, `tool`, `import`

Unknown fields, including `transcript`, `prompt`, and `api_key`, are rejected. This only analyzes claimed metadata; upstream speaker diarization/identity, intent classification and artifact verification remain to be implemented.

## Existing Selma command-core integration

Four tools are registered through the existing audited, permissioned router, accessed via `POST /api/selma0/tools/execute/v1` on loopback only:

- `collab.assess`: read-only assessment
- `collab.suggest_policy`: read-only dataset-derived suggestions
- `collab.record_observation`: write, requires `approved: true`
- `collab.apply_policy`: write, requires `approved: true`, allowlisted values and `expected_revision`

Example request body:

```json
{
  "tool": "collab.assess",
  "arguments": {
    "turns": [
      {"speaker_id": "gemini", "action_kind": "ack", "source_kind": "voice_transcript"},
      {"speaker_id": "chatgpt", "action_kind": "handoff", "source_kind": "voice_transcript"},
      {"speaker_id": "gemini", "action_kind": "ack", "source_kind": "voice_transcript"}
    ]
  }
}
```

Passing these metadata entries through the existing command router causes the local audit log to contain those labeled fields; no raw transcript is required or accepted. Because the host `127.0.0.1` does not prove who called the API, a browser extension must use additional authenticated transport/token exchange and strict origin checking before data is accepted. Browser extension ingestion is not enabled by this module.

## Local dataset and policy

Configuration and dataset are created lazily under `~/.selma0/collaboration_v1/` (or `SELMA0_COLLAB_DATA_DIR_V1`) with private directory permissions. SQLite records *only* an SHA-256 fingerprint of normalized metadata, feedback label, aggregate signals, count, revision and timestamp. Policy uses revisioned JSON with bounded thresholds, and policy history is stored locally.

This dataset is **behavioral feedback**, not synthetic-consciousness training. Feedback labels are reported by the caller and should be validated by the operator before policy promotion. The policy never changes OS permissions, authentication, network access, or security controls.

## Test

`python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v`

Portable unit tests do not prove Android/Termux permissions, a live Gemini connection, Chrome extension operation, or an effective speech-to-speaker classifier.
