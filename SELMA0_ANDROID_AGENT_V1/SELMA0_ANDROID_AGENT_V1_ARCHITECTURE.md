# SELMA0_ANDROID_AGENT_V1 Architecture

## Objective
Selma.0 is an Android 13+ offline-first / online-capable agent assistant. The active V1 architecture keeps the command core compatible with Termux and Python's standard library while adding explicit capability policy, auditability, and controlled migration tooling.

## Active runtime path

User -> local web UI -> `selma0_runtime_command_core_android_v1.py` -> command router -> permission policy -> registered tool/runtime capability -> audit log -> SQLite persistence.

Chat is also a registered command capability (`selma.chat`) because it persists conversation memory and may invoke the configured online fallback. It therefore requires the explicit confirmation supplied by the user-initiated UI turn instead of bypassing the command policy.

The older `selma0_runtime_android_v1.py` remains the underlying chat/memory/LLM implementation used by the command-core wrapper; it is not the production HTTP policy boundary.

## Command core

The V1 command core is composed of:

- `selma0_command_router_android_v1.py` - validates and dispatches registered capabilities.
- `selma0_permission_engine_android_v1.py` - fail-closed risk and approval policy.
- `selma0_tool_registry_android_v1.py` - bounded capability registry.
- `selma0_audit_log_android_v1.py` - append-only, hash-chained audit events with secret redaction and replay lookup.
- `selma0_runtime_command_core_android_v1.py` - HTTP boundary and registered runtime/safety/migration endpoints.

Read capabilities may execute without write approval. `write` and `external_effect` capabilities require explicit approval. Mutating/external-effect requests use persistent request IDs and canonical argument fingerprints to suppress duplicate execution safely.

Before an approved mutating action executes, the full audit chain is verified from genesis to tail. Corrupt or tampered audit history blocks mutation rather than silently starting a new trusted chain.

## Network boundary

The default bind address is `127.0.0.1:8765` and remains device-local.

Non-loopback binding fails closed unless `SELMA0_ALLOW_NONLOOPBACK_V1=1` is explicitly configured after an authenticated transport boundary is in place. HTTP Host and browser Origin checks also fail closed; permitted non-loopback hostnames must be listed in `SELMA0_ALLOWED_HTTP_HOSTS_V1`.

Legacy `/api/selma0/*` passthrough is disabled. Command-core API routes must be explicitly registered.

## Local command-core API

Read endpoints:

- `GET /` - mobile chat UI inherited from the base runtime.
- `GET /api/selma0/status/v1` - runtime plus command-core status.
- `GET /api/selma0/tools/v1` - registered capability status.
- `GET /api/selma0/tools/audit/v1` - recent command audit events.

Command/mutation endpoints:

- `POST /api/selma0/tools/execute/v1` - generic registered-tool execution.
- `POST /api/selma0/chat/v1` - approved Selma chat turn through `selma.chat`.
- `POST /api/selma0/replika/preview/v1` - preview a user-authorized local Replika archive.
- `POST /api/selma0/replika/import/v1` - confirmed migration import.
- `POST /api/selma0/safety/incident/v1` - record an authorized safety incident.
- `POST /api/selma0/safety/profile/v1` - confirmed safety-profile update.
- `POST /api/selma0/safety/sos/v1` - confirmed external-effect SOS workflow.

Unregistered `/api/selma0/*` routes return 404 instead of falling through to the legacy handler.

## Offline inference

The default local endpoint is:

`http://127.0.0.1:8080/v1`

It is intentionally OpenAI-compatible so a local llama.cpp-compatible Android server can be swapped without changing Selma's base runtime code.

Environment variables:

- `SELMA0_LOCAL_BASE_URL_V1`
- `SELMA0_LOCAL_MODEL_V1`
- `SELMA0_LLM_TIMEOUT_V1`

## Online fallback

Online access is disabled unless explicitly configured. Set:

- `SELMA0_ONLINE_BASE_URL_V1`
- `SELMA0_ONLINE_MODEL_V1`
- `SELMA0_ONLINE_API_KEY_V1`

If the local endpoint responds, no online request is made.

## Reciprocal empathy cognition (V1)

The base chat runtime composes a fixed, non-autonomous cognition preconfiguration
from `selma0_reciprocal_empathy_android_v1.py`. It considers the intended
impact of each response and labels its observed outcome as unverified until
explicit user feedback is recorded.

The `selma.empathy.feedback` capability is registered as `write` through
the existing command router. Valid categorical outcomes are stored locally
with user-reported provenance. Free-text feedback is never inserted into the
system prompt. This changes neither permissions nor device capabilities.
See `SELMA0_RECIPROCAL_EMPATHY_V1.md` for behavior, limitations, and tests.

## Persistent memory

SQLite database:

`~/SELMA0_ANDROID_AGENT_V1/selma0_data_android_v1/selma0_memory_android_v1.sqlite3`

WAL mode is enabled for resilience. V1 stores conversation events and route metadata. Replika migration records preserve provider/source provenance and use persistent deduplication so repeating the same authorized import does not duplicate historical memory.

## Replika migration boundary

`skills/replika_migration_v1` imports only archives the user is authorized to access. The SSH/stdin bridge receives data from a host/device the user controls, stages it locally with private file permissions, records a SHA-256 digest, previews by default, and requires explicit confirmation for import.

The skill does not scrape private Replika endpoints, collect account credentials, or claim access to proprietary hidden model/personality state.

## Validation and deployment

### Android / Termux

Production target and real runtime environment. `selma0_bootstrap_termux_android_v1.sh` installs the command-core stack. `selma0_smoke_test_android_v1.sh` compiles the agent, runs the unit/regression suite, launches an isolated local runtime, probes status/tool endpoints, and shuts it down.

### GitHub Actions

The active `Selma Android Build` workflow validates command-core changes with Python 3.12 compile and unittest jobs for pull requests and the `selma-command-core-v1` branch. Android APK assembly remains separately gated.

Linux CI validates portable Python behavior; Android permissions and Termux-specific/device effects still require the device smoke/integration gate.

## Next production layers

1. Complete a trustworthy command-core CI run and Android/Termux smoke test, then promote the command-core PR.
2. Local llama.cpp Android launcher and model-selection profile based on available RAM/storage.
3. Streaming token responses and cancellation.
4. Plugin adapters for approved external services through the same registry/permission/audit boundary.
5. RAG memory using compact local embeddings only when hardware permits.
6. Offline speech-to-text and text-to-speech modules loaded on demand.
7. Native Android shell/foreground-service wrapper after the Termux runtime is stable.
8. Signed APK/AAB packaging and Android permission UX.
9. CrowRF/DeepPinpoint sensing integration with strict measured-vs-inferred provenance.

## Design rules

- Every Selma-generated project artifact uses the `SELMA0_..._V#` namespace.
- Offline inference is attempted before online inference.
- Network use is explicit and configurable.
- Model output never directly executes arbitrary code; capabilities are routed through registered executors.
- Mutating or external-effect capabilities fail closed without approval and a trusted audit chain.
- Production sensor measurements are never replaced with invented/random telemetry; inferred values remain labeled as inference.
- Secrets remain environment variables and are never committed.
- Heavy modules are loaded only when required.
