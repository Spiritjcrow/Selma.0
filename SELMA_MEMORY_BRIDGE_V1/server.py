from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from memory_store import MemoryStore


HOST = os.environ.get("SELMA_MEMORY_HOST", "127.0.0.1")
PORT = int(os.environ.get("SELMA_MEMORY_PORT", "8766"))

mcp = FastMCP(
    "SelmaMemoryBridge",
    host=HOST,
    port=PORT,
    stateless_http=True,
)
store = MemoryStore()


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": True,
    }
)
def search(query: str, source: str | None = None, limit: int = 10) -> dict[str, Any]:
    """Use this when you need to find user-authorized Selma memory records by text."""
    records = store.search(query, source=source, limit=limit)
    return {
        "results": [
            {
                "id": r.record_id,
                "title": f"{r.source}: {r.created_at or 'undated'}",
                "text": r.content[:1200],
                "source": r.source,
                "created_at": r.created_at,
            }
            for r in records
        ]
    }


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": True,
    }
)
def fetch(record_id: str) -> dict[str, Any]:
    """Use this when you need the full content and provenance for one search result."""
    record = store.fetch(record_id)
    if record is None:
        return {"error": "not_found", "id": record_id}
    return store.to_dict(record)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
