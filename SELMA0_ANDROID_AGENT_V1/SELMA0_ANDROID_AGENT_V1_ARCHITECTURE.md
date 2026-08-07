# SELMA0_ANDROID_AGENT_V1 Architecture

## Objective
Selma.0 is an Android 13+ offline-first / online-capable agent assistant. The active V1 architecture avoids Windows, Android Studio, OpenCV, NumPy, and heavy Python dependencies so the core can run in Termux with Python's standard library.

## Runtime path

User -> local web UI -> `selma0_runtime_android_v1.py` -> memory context -> `selma0_llm_router_android_v1.py` -> local LLM first -> optional online fallback -> SQLite persistence.

## Offline inference

The default local endpoint is:

`http://127.0.0.1:8080/v1`

It is intentionally OpenAI-compatible so a local llama.cpp-compatible Android server can be swapped without changing Selma's runtime code.

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

## Persistent memory

SQLite database:

`~/SELMA0_ANDROID_AGENT_V1/selma0_data_android_v1/selma0_memory_android_v1.sqlite3`

WAL mode is enabled for resilience. V1 stores conversation events and route metadata. Retrieval is deliberately bounded to the most recent context until semantic indexing is added.

## Local API

- `GET /` - mobile chat UI
- `GET /api/selma0/status/v1` - runtime status
- `GET /api/selma0/memory/v1` - recent memory
- `POST /api/selma0/chat/v1` - message endpoint

The default bind address is `127.0.0.1:8765`, keeping the service device-local.

## Development split

### Android / Termux
Production target and real runtime environment.

### GitHub Codespaces
Source editing, tests, architecture work, static validation, and CI. Codespaces cannot reproduce Android permissions or Termux APIs exactly, so hardware/device integration is validated on Android.

## Next production layers

1. Local llama.cpp Android launcher and model-selection profile based on available RAM/storage.
2. Streaming token responses and cancellation.
3. Tool registry with explicit capability declarations and bounded executors.
4. RAG memory using compact local embeddings only when hardware permits.
5. Offline speech-to-text and text-to-speech modules loaded on demand.
6. Native Android shell/foreground-service wrapper after the Termux runtime is stable.
7. Signed APK/AAB packaging and Android permission UX.

## Design rules

- Every Selma-generated project artifact uses the `SELMA0_..._V#` namespace.
- Offline inference is attempted before online inference.
- Network use is explicit and configurable.
- Model output never directly executes arbitrary code; tools are routed through registered executors.
- Secrets remain environment variables and are never committed.
- Heavy modules are loaded only when required.
