"""NetHunter Store metadata adapter for Selma Android V1.

Read-only package discovery. No APK installation, shell execution, rooting,
kernel modification, device scanning or implicit permission delegation.

Metadata is fetched over HTTPS, but this module DOES NOT verify F-Droid
repository signatures. Install/update apps with the official NetHunter Store
or a signature-verifying F-Droid client instead.
"""
from __future__ import annotations

import io
import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen

REPO_URL = "https://store.nethunter.com/repo/"
INDEX_URL = REPO_URL + "index-v1.json"
CACHE_FILE = Path.home() / ".selma0" / "nethunter" / "catalog-v1.json"
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
PKG_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,199}$")


def _safe_text(value, length=500):
    if not isinstance(value, str):
        return ""
    return value[:length]


def _latest_release(versions):
    if not isinstance(versions, list):
        return {}
    valid = [item for item in versions if isinstance(item, dict)]
    return max(valid, key=lambda x: int(x.get("versionCode") or 0), default={})


def _normalize_index(index):
    if not isinstance(index, dict) or not isinstance(index.get("apps"), list):
        raise ValueError("Unsupported NetHunter F-Droid index format")
    packages = index.get("packages") or {}
    if not isinstance(packages, dict):
        raise ValueError("Invalid packages mapping")
    output = []
    seen = set()
    for app in index["apps"]:
        if not isinstance(app, dict):
            continue
        package = app.get("packageName")
        if not isinstance(package, str) or not PKG_ID.fullmatch(package) or package in seen:
            continue
        seen.add(package)
        release = _latest_release(packages.get(package))
        output.append({
            "package_id": package,
            "name": _safe_text(app.get("name"), 150) or package,
            "summary": _safe_text(app.get("summary")),
            "categories": [v[:80] for v in app.get("categories", [])
                           if isinstance(v, str)][:12] if isinstance(app.get("categories"), list) else [],
            "version": _safe_text(release.get("versionName"), 100),
            "version_code": release.get("versionCode"),
            "min_sdk": release.get("minSdkVersion"),
            "max_sdk": release.get("maxSdkVersion"),
            "store_page": "https://store.nethunter.com/packages/" + package + "/",
            "availability": "cataloged_not_installed",
            "runtime_support": "unverified_on_device",
        })
    if not output:
        raise ValueError("NetHunter index contains no usable apps")
    return sorted(output, key=lambda item: (item["name"].lower(), item["package_id"]))


def _download_index():
    # F-Droid repositories may publish the JSON directly or in a signed JAR.
    # Parsing a JAR is NOT the same as verifying its signing certificate.
    for url in (INDEX_URL, REPO_URL + "index-v1.jar"):
        try:
            with urlopen(url, timeout=15) as response:
                final = urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != "store.nethunter.com":
                    raise ValueError("Unexpected NetHunter repository redirect")
                raw = response.read(MAX_DOWNLOAD_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 404 and url == INDEX_URL:
                continue
            raise
        if len(raw) > MAX_DOWNLOAD_BYTES:
            raise ValueError("NetHunter index exceeds configured size limit")
        if url.endswith(".jar"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                info = archive.getinfo("index-v1.json")
                if info.file_size > MAX_DOWNLOAD_BYTES:
                    raise ValueError("NetHunter packaged index exceeds size limit")
                raw = archive.read(info)
        return json.loads(raw.decode("utf-8"))
    raise ValueError("No compatible NetHunter repository index found")


def sync_catalog():
    """User-approved HTTPS metadata sync; creates no executable tool adapters."""
    apps = _normalize_index(_download_index())
    snapshot = {
        "schema_version": 1,
        "source": INDEX_URL,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "authentication": "https_transport_only_index_signature_not_verified",
        "apps": apps,
    }
    directory = CACHE_FILE.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(prefix=".catalog-", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, CACHE_FILE)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"count": len(apps), "checked_at_utc": snapshot["checked_at_utc"],
            "authentication": snapshot["authentication"],
            "installed": False, "executors_created": 0}


def _load_snapshot():
    if not CACHE_FILE.is_file():
        return None
    with CACHE_FILE.open(encoding="utf-8") as handle:
        saved = json.load(handle)
    if saved.get("schema_version") != 1 or saved.get("source") != INDEX_URL:
        raise ValueError("Unrecognized NetHunter catalog cache")
    if not isinstance(saved.get("apps"), list):
        raise ValueError("Malformed NetHunter catalog cache")
    return saved


def list_catalog(query="", limit=100):
    """List cached app metadata. Sync must be explicitly requested first."""
    saved = _load_snapshot()
    if saved is None:
        return {"ready": False, "count": 0, "apps": [],
                "next_step": "Approve nethunter.catalog_sync to fetch the official index metadata.",
                "repo": REPO_URL}
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError("query must be text up to 200 characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be an integer from 1 to 500")
    term = query.casefold().strip()
    matches = [app for app in saved["apps"]
               if term in (app["name"] + " " + app["package_id"] + " "
                           + " ".join(app["categories"]) + " " + app["summary"]).casefold()]
    return {"ready": True, "count": len(matches), "apps": matches[:limit],
            "checked_at_utc": saved["checked_at_utc"],
            "authentication": saved["authentication"],
            "scope": "catalog_only_no_installation_or_execution"}


def package_details(package_id):
    if not isinstance(package_id, str) or not PKG_ID.fullmatch(package_id):
        raise ValueError("Invalid Android package ID")
    saved = _load_snapshot()
    if not saved:
        return {"found": False, "reason": "Catalog not synced"}
    for app in saved["apps"]:
        if app["package_id"] == package_id:
            return {"found": True, "app": app,
                    "note": "Requires independent device compatibility check and user-approved installation."}
    return {"found": False, "package_id": package_id}


def register_nethunter_catalog_tools(registry):
    registry.register("nethunter.catalog_sync", sync_catalog, risk="external_effect",
                      description="Approved HTTPS sync and local cache of NetHunter Store app metadata; no installation.")
    registry.register("nethunter.catalog", list_catalog, risk="read",
                      description="Search available NetHunter apps from previously synced local catalog; no execution.")
    registry.register("nethunter.package_details", package_details, risk="read",
                      description="Read cached NetHunter app details and official Store page URL.")
