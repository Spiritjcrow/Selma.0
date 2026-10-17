#!/usr/bin/env python3
"""SpaceGhost EarthWatch: catalog metadata monitoring, never an animal/person tracker.

Queries two public STAC APIs for scene metadata in a configured area and rolling
time window. No purchased imagery, hidden object identification, or form submission.
"""
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CENTER = (27.9359629, -97.1286663)  # lat, lon; search pin, not a surveyed boundary
RADIUS_METERS = 1300
LOOKBACK_DAYS = 42
CATALOGS = {
    "earth-search": "https://earth-search.aws.element84.com/v1/search",
    "planetary-computer": "https://planetarycomputer.microsoft.com/api/stac/v1/search",
}
COLLECTIONS = ("sentinel-2-l2a", "landsat-c2-l2", "naip")
STATE_FILE = ROOT / "state.json"
REPORT_FILE = ROOT / "latest.md"
USER_AGENT = "SelmaOS-SpaceGhost-EarthWatch/1.0 (metadata-only; public catalogs)"
MAX_SCENES = 900


def now_utc():
    return datetime.now(timezone.utc)


def iso(d):
    return d.isoformat(timespec="seconds").replace("+00:00", "Z")


def bounds():
    lat, lon = CENTER
    dlat = RADIUS_METERS / 111320
    dlon = RADIUS_METERS / (111320 * math.cos(math.radians(lat)))
    return [round(lon - dlon, 7), round(lat - dlat, 7),
            round(lon + dlon, 7), round(lat + dlat, 7)]


def request_json(url, payload, headers=None, retries=3):
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={
        "Accept": "application/geo+json, application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        **(headers or {}),
    }, method="POST")
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=35) as response:
                return json.loads(response.read(8_000_000))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"{url}: {type(exc).__name__}: {exc}") from exc
            time.sleep(attempt + 1)


def fetch_collection(url, collection, start, end):
    payload = {
        "collections": [collection],
        "bbox": bounds(),
        "datetime": f"{iso(start)}/{iso(end)}",
        "limit": 100,
    }
    results = []
    # Follow only bounded POST pages on the same trusted catalog origin.
    for _ in range(6):
        page = request_json(url, payload)
        results.extend(page.get("features", []))
        links = page.get("links", [])
        next_link = next((x for x in links if x.get("rel") == "next"), None)
        if not next_link:
            break
        if (next_link.get("method", "GET").upper() != "POST"
                or next_link.get("href", "").split("/search")[0]
                != url.split("/search")[0]):
            # Catalog variants sometimes use GET links. Rather than following
            # arbitrary links, stop and record a warning via caller.
            break
        payload = next_link.get("body") or payload
    return results


def simplify(item, collection, catalog):
    scene_id = item.get("id")
    props = item.get("properties") or {}
    acquired = props.get("datetime") or props.get("start_datetime")
    if not scene_id or not acquired:
        return None
    cloud = props.get("eo:cloud_cover")
    if not isinstance(cloud, (float, int)):
        cloud = None
    link = next((x.get("href") for x in item.get("links", [])
                 if x.get("rel") == "self" and x.get("href", "").startswith("https://")), "")
    return {
        "key": f"{collection}:{scene_id}",
        "collection": collection,
        "scene_id": str(scene_id),
        "acquired": acquired,
        "cloud_pct": round(cloud, 1) if cloud is not None else None,
        "catalog": catalog,
        "link": link,
    }


def report_text(stamp, seen, fresh, warnings, scanned):
    lat, lon = CENTER
    lines = [
        "# SpaceGhost EarthWatch: metadata catalog",
        "",
        f"Checked UTC: {stamp}",
        f"Pin: {lat:.7f}, {lon:.7f} (approximate, not a surveyed parcel)",
        f"Approximate search radius: {RADIUS_METERS} m; rolling window: {LOOKBACK_DAYS} days.",
        f"Catalog items examined this run: {scanned}; newly indexed: {len(fresh)}.",
        f"Total remembered scene IDs: {len(seen)}.",
        "",
        "## Recently indexed scenes",
        "",
        "| Acquisition (UTC) | Collection | Cloud % (whole scene) | Catalog |",
        "|---|---|---:|---|",
    ]
    for scene in sorted(fresh, key=lambda v: v["acquired"], reverse=True)[:50]:
        name = scene["collection"].replace("|", " ")
        cloud = "unknown" if scene["cloud_pct"] is None else str(scene["cloud_pct"])
        label = f"[{scene['catalog']}]({scene['link']})" if scene["link"] else scene["catalog"]
        lines.append(f"| {scene['acquired']} | {name} | {cloud} | {label} |")
    if not fresh:
        lines.append("| No new metadata found | | | |")
    lines += [
        "",
        "## Provider / interpretation notes",
        "",
        "- Sentinel-2 is typically 10–60 m per pixel; Landsat about 30 m for multispectral imagery.",
        "- NAIP aerial photographs may be higher resolution but are not captured daily.",
        "- A catalog hit is a scene acquisition record, not proof that an object or lost pet was seen.",
        "- Cloud percentage describes the scene, not necessarily this small search area.",
        "- LiDAR is historic terrain data; this script does not acquire new LiDAR surveys.",
        "- No provider forms, messages or emails are submitted automatically.",
        "",
        "## Warnings",
    ]
    lines.extend([f"- {x}" for x in warnings] or ["- None"])
    lines += [
        "",
        "## Imagery update requests",
        "",
        "Google Earth offers an official imagery update request through its Help menu:",
        "https://developers.google.com/maps/documentation/earth/tell-us-about-a-problem",
        "",
        "Suggested request: 'Please review outdated aerial/satellite imagery near "
        f"{lat:.7f}, {lon:.7f} in Aransas Pass, Texas, within about {RADIUS_METERS} m. "
        "Please show the actual image acquisition date and consider newer high-resolution "
        "coverage where available. This is a local search and mapping need.'",
        "",
        "No request is considered submitted until a provider acknowledges receipt.",
        "",
    ]
    return "\n".join(lines)


def issue_alert(scene_list, stamp):
    token = os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not token or not repo:
        print("No GitHub issue credentials: report only.")
        return
    title = f"SpaceGhost: {len(scene_list)} usable new imagery scene(s) — {stamp[:10]}"
    rows = []
    for scene in scene_list[:15]:
        cloud = "n/a" if scene["cloud_pct"] is None else str(scene["cloud_pct"]) + "%"
        safe_url = scene["link"] if scene["link"].startswith("https://") else ""
        rows.append(f"- {scene['acquired']}: {scene['collection']} "
                    f"(scene cloud {cloud}) {safe_url}")
    if len(scene_list) > 15:
        rows.append(f"- Plus {len(scene_list) - 15} more. See spaceghost/latest.md.")
    body = "\n".join([
        "New scene **metadata**, not confirmed pet or person detections.",
        "The reported cloud cover is for the entire source scene.",
        "",
        *rows,
        "",
        "Full report: spaceghost/latest.md in this private repository.",
        "Provider request drafts are maintained in that report; none were submitted.",
    ])
    req = Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps({"title": title, "body": body}).encode(),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urlopen(req, timeout=25) as response:
        if response.status != 201:
            raise RuntimeError(f"GitHub issue creation returned {response.status}")
    print(f"Notification issue created for {len(scene_list)} scene(s).")


def main():
    end = now_utc()
    start = end - timedelta(days=LOOKBACK_DAYS)
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    old = state.get("seen", {})
    unique = {}
    warnings = []
    successful = 0
    scanned = 0
    for source, url in CATALOGS.items():
        for coll in COLLECTIONS:
            try:
                raw = fetch_collection(url, coll, start, end)
                successful += 1
                scanned += len(raw)
                for record in raw:
                    scene = simplify(record, coll, source)
                    if not scene:
                        continue
                    if scene["key"] not in unique:
                        unique[scene["key"]] = scene
            except Exception as exc:
                warnings.append(f"{source}/{coll}: {str(exc)[:220]}")
                print(f"Warning: {warnings[-1]}", file=sys.stderr)
    if successful == 0:
        raise RuntimeError("Every catalog query failed; retaining previous state.")
    new = [v for k, v in unique.items() if k not in old]
    # Higher-resolution NAIP, and relatively cloud-free broad-area scenes:
    notable = [x for x in new if x["collection"] == "naip"
               or (x["cloud_pct"] is not None and x["cloud_pct"] <= 35)]
    # Alert before recording IDs: failed GitHub notification retries next run.
    if notable:
        issue_alert(sorted(notable, key=lambda v: v["acquired"], reverse=True), iso(end))
    combined = dict(old)
    for scene in new:
        combined[scene["key"]] = scene
    combined = dict(sorted(combined.items(),
                           key=lambda kv: kv[1].get("acquired", ""), reverse=True)[:MAX_SCENES])
    STATE_FILE.write_text(json.dumps({
        "last_checked_utc": iso(end),
        "seen": combined,
    }, indent=2) + "\n")
    REPORT_FILE.write_text(report_text(iso(end), combined, new, warnings, scanned))
    print(f"Scanned={scanned} new={len(new)} notable={len(notable)} "
          f"warnings={len(warnings)} remembered={len(combined)}")


if __name__ == "__main__":
    main()
