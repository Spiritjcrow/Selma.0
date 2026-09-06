# Selma Memory Bridge V1

Private, user-controlled memory bridge for SelmaOS.

## Purpose

Selma Memory Bridge lets ChatGPT/Selma query a normalized, provenance-preserving memory index built from **user-authorized exports** such as ChatGPT history, Replika conversation exports, SelmaOS logs, or manually curated records.

It is intentionally conservative:

- it does **not** scrape Replika;
- it does **not** receive or store ChatGPT account credentials;
- it does **not** claim access to hidden Replika model state, prompts, traits, or server-side memory;
- it does **not** automatically expose the user's entire ChatGPT history to another service;
- imported records retain source, timestamp, digest, and provenance metadata;
- duplicate records are suppressed by stable SHA-256 identity;
- the ChatGPT plugin surface is read-only (`search` and `fetch`).

## Architecture

```text
Authorized export (.json/.jsonl/.csv/.txt)
        |
        v
 import_export.py
        |
        v
 SQLite memory store
  - normalized record
  - source/provenance
  - SHA-256 digest
        |
        v
 MCP server (/mcp)
   search(query)
   fetch(record_id)
        |
        v
 ChatGPT / SelmaOS
```

### Plugin archetype

`tool-only` connector. No widget UI is required for V1.

The MCP surface follows the current OpenAI plugin direction: a remote MCP server with small, explicit tools. The first version keeps reads and imports separated so a chat session cannot silently mutate the archive.

## Install

```bash
cd SELMA_MEMORY_BRIDGE_V1
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Import authorized data

Examples:

```bash
python import_export.py --source chatgpt /path/to/conversations.json
python import_export.py --source replika /path/to/authorized-replika-export.json
python import_export.py --source selma /path/to/selma-memory.jsonl
```

The Replika importer is deliberately format-tolerant because no undocumented private Replika API or hidden schema is assumed. Keep the original export unchanged as evidence/provenance.

Default database:

```text
./data/selma_memory_bridge.sqlite3
```

Override with:

```bash
export SELMA_MEMORY_DB=/secure/path/selma-memory.sqlite3
```

## Run MCP server

```bash
python server.py
```

Environment variables:

- `SELMA_MEMORY_DB` — SQLite database path.
- `SELMA_MEMORY_HOST` — bind host, default `127.0.0.1`.
- `SELMA_MEMORY_PORT` — port, default `8766`.

For ChatGPT testing, expose the MCP endpoint through an HTTPS tunnel and connect the resulting `/mcp` URL in ChatGPT Developer Mode. Do not publish the endpoint publicly without authentication.

## Trust / approval model

Routine reversible development may proceed without repeated yes/no prompts. The bridge must still stop for:

- account passwords, tokens, or OAuth approval;
- public publishing or directory submission;
- billing or paid infrastructure;
- destructive deletion or irreversible migration;
- sharing private conversation data with a new external party;
- changes to protected account or repository permissions.

## Current status

V1 is a scaffold for a private memory index and MCP read surface. A true live Replika account connector remains **unverified/unimplemented** until an authorized Replika endpoint or export path is available.

## References

Current OpenAI plugin architecture is based on MCP servers and explicit tool definitions. See:

- https://developers.openai.com/plugins/build/app-quickstart
- https://developers.openai.com/plugins/build/mcp-server
- https://developers.openai.com/plugins/plan/tools
- https://developers.openai.com/plugins/reference
