"""Read-only YouTube Data API v3 adapter: no video scraping or arbitrary URL fetching."""
import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

VID = re.compile(r"^[A-Za-z0-9_-]{11}$")
API = "https://www.googleapis.com/youtube/v3/"

def parse_id(value):
    value = value.strip()
    if VID.fullmatch(value):
        return value
    u = urlparse(value)
    if u.scheme != "https" or u.username or u.password or u.port:
        raise ValueError("Expected HTTPS YouTube URL or 11-character ID")
    host = (u.hostname or "").lower()
    parts = [p for p in u.path.split("/") if p]
    found = None
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if u.path == "/watch":
            found = parse_qs(u.query).get("v", [None])[0]
        elif len(parts) == 2 and parts[0] in ("shorts", "embed", "live"):
            found = parts[1]
    elif host == "youtu.be" and len(parts) == 1:
        found = parts[0]
    if not found or not VID.fullmatch(found):
        raise ValueError("Invalid YouTube URL")
    return found

def watch_link(value, timestamp=0):
    vid = parse_id(value)
    if not 0 <= timestamp <= 864000:
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
            data = json.load(f)
    except HTTPError as e:
        raise RuntimeError(f"YouTube API returned HTTP {e.code}") from None
    except (URLError, TimeoutError, ValueError) as e:
        raise RuntimeError(f"YouTube API request failed: {type(e).__name__}") from None
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected API response")
    return data

def search(query, limit=10, *, get=google_get):
    if not 1 <= len(query) <= 180 or not 1 <= limit <= 25:
        raise ValueError("Invalid search query or result limit")
    response = get("search", {"part":"snippet", "type":"video", "safeSearch":"moderate", "q":query, "maxResults":limit})
    output = []
    for entry in response.get("items", []):
        vid = entry.get("id", {}).get("videoId", "")
        if not VID.fullmatch(vid):
            continue
        s = entry.get("snippet", {})
        output.append({"video_id":vid, "watch_url":watch_link(vid), "title":s.get("title", ""), "channel":s.get("channelTitle",""), "published_at":s.get("publishedAt",""), "description_excerpt":s.get("description","")[:500]})
    return output

def details(url_or_id, *, get=google_get):
    vid = parse_id(url_or_id)
    response = get("videos", {"part":"snippet,contentDetails,statistics", "id":vid})
    items = response.get("items", [])
    if not items:
        return {"found":False, "video_id":vid, "watch_url":watch_link(vid)}
    s = items[0].get("snippet", {})
    return {"found":True, "video_id":vid, "watch_url":watch_link(vid), "title":s.get("title",""), "channel":s.get("channelTitle",""), "published_at":s.get("publishedAt",""), "description":s.get("description","")[:3000], "duration":items[0].get("contentDetails",{}).get("duration",""), "view_count":items[0].get("statistics",{}).get("viewCount"), "inspection_status":"metadata only; no video frames or audio analyzed"}

def evidence_checklist(url_or_id, timestamp=0):
    return {"video_url": watch_link(url_or_id, timestamp), "timestamp_seconds": timestamp, "status":"unverified", "direct_observation":"not viewed", "review": ["Continuity and potential cuts", "Possible concealed supports", "Air movement and pressure", "Camera perspective and timing", "Known object mass and scale", "Independent test with multiple angles"], "note":"A metadata lookup cannot prove the physical event depicted."}
