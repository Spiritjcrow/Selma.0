# Selma Webflow University connector

Standalone Python MCP stdio and FastAPI localhost bridge, with SQLite WAL and FTS5 cached search. Public course metadata only. Not affiliated with Webflow.

Install: `python -m pip install -r requirements.txt`

MCP: `python webflow_university_connector.py` (register as stdio server in compatible MCP client).

HTTP: set `CONNECTOR_BEARER_TOKEN` to a securely generated persistent secret, then `CONNECTOR_MODE=http python webflow_university_connector.py`. API binds to `127.0.0.1:8095`.

Endpoints: `GET /health`, `POST /v1/sync`, `POST /v1/search`, `GET /v1/outline?url=...`.

Tests: `python -m unittest discover -s tests -v`.

Offline searches use cached catalog; outlines and refresh need network. Validate live Webflow page structure before relying on course completeness.
