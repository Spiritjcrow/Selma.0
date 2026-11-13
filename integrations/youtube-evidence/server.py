"""Local MCP adapter. Never expose publicly without access-controlled HTTPS gateway."""
import json
from mcp.server.fastmcp import FastMCP
from youtube_client import search, details, evidence_checklist, watch_link
mcp = FastMCP("Selma YouTube Evidence Research")

@mcp.tool()
def youtube_search(query: str, max_results: int=10) -> str:
    """Search YouTube metadata; requires server-side YOUTUBE_API_KEY."""
    return json.dumps(search(query, max_results), ensure_ascii=False)

@mcp.tool()
def youtube_video_metadata(url_or_id: str) -> str:
    """Get public video metadata; does not inspect frames or audio."""
    return json.dumps(details(url_or_id), ensure_ascii=False)

@mcp.tool()
def youtube_evidence_checklist(url_or_id: str, timestamp_seconds: int=0) -> str:
    """Generate an objective unverified media-review checklist."""
    return json.dumps(evidence_checklist(url_or_id, timestamp_seconds), ensure_ascii=False)

@mcp.tool()
def youtube_timestamp_link(url_or_id: str, timestamp_seconds: int=0) -> str:
    """Generate a timestamped watch link without a YouTube API key."""
    return watch_link(url_or_id, timestamp_seconds)

if __name__ == "__main__":
    mcp.run(transport="stdio")
