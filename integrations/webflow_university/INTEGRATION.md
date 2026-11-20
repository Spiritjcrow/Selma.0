# Webflow University education provider (staging)

Integration branch: `feature/webflow-university-connector-v1-1`.

The standalone v1.1 Python package has been generated as a downloadable ZIP in the ChatGPT conversation. This repository entry records the integration target; **the Python package has not yet been committed here**.

## Planned layout

`integrations/webflow_university/`: connector module, requirements, tests and README.

## Contract

- MCP stdio: `sync_webflow_courses`, `search_webflow_courses`, `get_course_outline`.
- Local REST: `GET /health`, `POST /v1/sync`, `POST /v1/search`, `GET /v1/outline`.
- Local-only HTTP listener on port 8095, bearer token required.
- SQLite WAL and FTS5, cached metadata search offline after successful sync.
- No changes to Android Gradle workflows, signing, secrets, or existing agent runtime.

## Verification outstanding

Dependency installation, unit tests, live Webflow HTML parsing, MCP handshake, and Android/Termux execution. Do not describe as deployed or production ready.
