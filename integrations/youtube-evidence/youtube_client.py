"""Read-only YouTube Data API v3 adapter: no video scraping or arbitrary URL fetching."""
import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

VID = re.compile(r"^[A-Za-z0-9_-]{11}$")
API = "https://www.googleapis.com/youtube/v3/"
# Bound untrusted API response bytes before JSON decoding to avoid memory exhaustion.
MAX_API_RESPONSE_BYTES = 2_097_152

def _unique_json_object(pairs):
    """Reject ambiguous duplicate keys at every depth of an API JSON response."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result

def parse_id(value):
    # MCP inputs are untrusted. Bound work and return a stable validation error.
    if type(value) is not str or len(value) > 2048:
        raise ValueError("Expected HTTPS YouTube URL or 11-character ID")
    # urlparse strips leading C0 controls, while strip() can erase C1 NEL
    # (U+0085). Reject these raw control characters before normalization.
    if any((ord(c) < 32 and c not in " \t\n\r")
           or 0x7F <= ord(c) <= 0x9F for c in value):
        raise ValueError("Invalid YouTube URL")
    value = value.strip()
    # urllib.parse silently removes embedded TAB/CR/LF, which can rewrite
    # a malformed evidence URL into a different valid YouTube identifier.
    if any(c in value for c in "\t\n\r"):
        raise ValueError("Invalid YouTube URL")
    if VID.fullmatch(value):
        return value
    try:
        u = urlparse(value)
        # Exact authority matching rejects credentials, ports (including :0
        # and an empty :), and deceptive host suffixes.
        authority = u.netloc.lower()
    except ValueError:
        raise ValueError("Invalid YouTube URL") from None
    if u.scheme != "https" or authority not in (
            "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"):
        raise ValueError("Expected HTTPS YouTube URL or 11-character ID")
    parts = [p for p in u.path.split("/") if p]
    found = None
    if authority in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if u.path == "/watch":
            ids = parse_qs(u.query, keep_blank_values=True).get("v", [])
            # Multiple video IDs are ambiguous provenance, even if one is valid.
            found = ids[0] if len(ids) == 1 else None
        elif len(parts) == 2 and parts[0] in ("shorts", "embed", "live"):
            found = parts[1]
    elif authority == "youtu.be" and len(parts) == 1:
        found = parts[0]
    if not found or not VID.fullmatch(found):
        raise ValueError("Invalid YouTube URL")
    return found

def watch_link(value, timestamp=0):
    vid = parse_id(value)
    if type(timestamp) is not int or not 0 <= timestamp <= 864000:
        raise ValueError("Invalid timestamp")
    return "https://www.youtube.com/watch?v=" + vid + (f"&t={timestamp}s" if timestamp else "")

def google_get(endpoint, params, *, opener=urlopen):
    if endpoint not in ("search", "videos"):
        raise ValueError("Unsupported endpoint")
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not configured as a server secret")
    target = API + endpoint + "?" + urlencode({**params, "key": key})
    try:
        with opener(target, timeout=15) as f:
            raw = f.read(MAX_API_RESPONSE_BYTES + 1)
        if len(raw) > MAX_API_RESPONSE_BYTES:
            raise ValueError("API response exceeds byte limit")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object)
    except HTTPError as e:
        raise RuntimeError(f"YouTube API returned HTTP {e.code}") from None
    except (URLError, TimeoutError, ValueError, RecursionError) as e:
        raise RuntimeError(f"YouTube API request failed: {type(e).__name__}") from None
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected API response")
    return data

def search(query, limit=10, *, get=google_get):
    # Reject booleans, fractional limits, and non-text queries before the API call.
    # Bound the raw input before trimming: a very long whitespace prefix can
    # otherwise pass the 180-character visible-query limit and reach urlencode.
    if (type(query) is not str or len(query) > 2048
            or not 1 <= len(query.strip()) <= 180
            or type(limit) is not int or not 1 <= limit <= 25):
        raise ValueError("Invalid search query or result limit")
    clean_query = query.strip()
    response = get("search", {"part":"snippet", "type":"video", "safeSearch":"moderate", "q":clean_query, "maxResults":limit})
    # A provider error/malformed response must not masquerade as zero results.
    if (type(response) is not dict or "error" in response
            or type(response.get("items")) is not list):
        raise RuntimeError("Unexpected YouTube search response")
    output = []
    for entry in response["items"]:
        if type(entry) is not dict or type(entry.get("id")) is not dict:
            continue
        vid = entry["id"].get("videoId")
        if type(vid) is not str or not VID.fullmatch(vid):
            continue
        s = entry.get("snippet", {})
        if type(s) is not dict:
            continue
        title = s.get("title", "")
        channel = s.get("channelTitle", "")
        published = s.get("publishedAt", "")
        description = s.get("description", "")
        if any(type(value) is not str for value in (title, channel, published, description)):
            continue
        output.append({"video_id":vid, "watch_url":watch_link(vid), "title":title, "channel":channel, "published_at":published, "description_excerpt":description[:500]})
        # Treat provider items as untrusted; maxResults is a request, not a
        # response-side bound. Count only validated entries toward the limit.
        if len(output) >= limit:
            break
    return output

def details(url_or_id, *, get=google_get):
    vid = parse_id(url_or_id)
    response = get("videos", {"part":"snippet,contentDetails,statistics", "id":vid})
    if (type(response) is not dict or "error" in response
            or type(response.get("items")) is not list):
        raise RuntimeError("Unexpected YouTube details response")
    items = response["items"]
    if not items:
        return {"found":False, "video_id":vid, "watch_url":watch_link(vid)}
    # The videos.list request is for exactly one ID. Multiple records make
    # the returned metadata ambiguous, even if the first record matches.
    if len(items) != 1:
        raise RuntimeError("Unexpected YouTube details response")
    item = items[0]
    if type(item) is not dict or item.get("id") != vid:
        raise RuntimeError("Unexpected YouTube details response")
    s = item.get("snippet", {})
    content = item.get("contentDetails", {})
    stats = item.get("statistics", {})
    if any(type(part) is not dict for part in (s, content, stats)):
        raise RuntimeError("Unexpected YouTube details response")
    title = s.get("title", "")
    channel = s.get("channelTitle", "")
    published = s.get("publishedAt", "")
    description = s.get("description", "")
    duration = content.get("duration", "")
    views = stats.get("viewCount")
    if (any(type(value) is not str for value in (title, channel, published, description, duration))
            or (views is not None and type(views) is not str)):
        raise RuntimeError("Unexpected YouTube details response")
    return {"found":True, "video_id":vid, "watch_url":watch_link(vid), "title":title, "channel":channel, "published_at":published, "description":description[:3000], "duration":duration, "view_count":views, "inspection_status":"metadata only; no video frames or audio analyzed"}

def evidence_checklist(url_or_id, timestamp=0):
    return {"video_url": watch_link(url_or_id, timestamp), "timestamp_seconds": timestamp, "status":"unverified", "direct_observation":"not viewed", "review": ["Continuity and potential cuts", "Possible concealed supports", "Air movement and pressure", "Camera perspective and timing", "Known object mass and scale", "Independent test with multiple angles"], "note":"A metadata lookup cannot prove the physical event depicted."}
