#!/usr/bin/env python3
"""Compare local APK bytes with a user-imported claimed receipt. Offline and read-only.

MATCH means only that local bytes agree with a self-declared metadata receipt;
it NEVER authenticates Codemagic, signs/releases an APK, or verifies installability.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import stat
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path

MAX_RECEIPT_BYTES = 100_000
CHUNK_BYTES = 1024 * 1024
HEX24 = re.compile(r"^[a-fA-F0-9]{24}$")
HEX40 = re.compile(r"^[a-fA-F0-9]{40}$")
HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")
APK_NAME = re.compile(r"^[A-Za-z0-9._-]{1,176}\.apk$")


class ReceiptError(ValueError):
    """Malformed/unsupported receipt or unreadable APK."""


def validate_receipt(receipt: object) -> dict:
    if not isinstance(receipt, dict) or set(receipt) != {
        "schema_version", "source_type", "attestation", "build"
    } or receipt["schema_version"] != 1 or receipt["source_type"] != "owner_import" or \
            receipt["attestation"] != "UNVERIFIED_USER_SUPPLIED":
        raise ReceiptError("receipt must be owner-imported and explicitly unverified")
    build = receipt["build"]
    if not isinstance(build, dict) or not {
        "app_id", "build_id", "workflow_id", "commit_sha", "status"
    }.issubset(build) or set(build) - {
        "app_id", "build_id", "workflow_id", "commit_sha", "status",
        "branch", "source_url", "started_utc", "finished_utc", "environment", "artifact"
    }:
        raise ReceiptError("build metadata is invalid or contains unknown fields")
    if not all(isinstance(build.get(k), str) and pat.fullmatch(build[k]) for k, pat in [
        ("app_id", HEX24), ("build_id", HEX24), ("commit_sha", HEX40)
    ]):
        raise ReceiptError("invalid build/commit IDs")
    workflow = build["workflow_id"]
    if not isinstance(workflow, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", workflow):
        raise ReceiptError("invalid workflow ID")
    if not isinstance(build["status"], str) or build["status"] not in {"unknown", "queued", "building", "finished", "failed", "cancelled"}:
        raise ReceiptError("invalid build status")
    if "branch" in build and (not isinstance(build["branch"], str) or
        not re.fullmatch(r"[A-Za-z0-9_./-]{1,160}", build["branch"])):
        raise ReceiptError("invalid branch")
    if "source_url" in build:
        if not isinstance(build["source_url"], str):
            raise ReceiptError("invalid source URL")
        try:
            u = urlsplit(build["source_url"])
            if u.scheme != "https" or u.hostname != "codemagic.io" or u.port is not None or \
                    u.username or u.password or not u.path.startswith("/app/") or u.query or u.fragment:
                raise ReceiptError("unapproved source URL")
        except ValueError as exc:
            raise ReceiptError("invalid source URL") from exc
    for key in ("started_utc", "finished_utc"):
        if key in build:
            value = build[key]
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*(?:Z|\+00:00)", value):
                raise ReceiptError("invalid UTC timestamp")
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if dt.utcoffset() != timezone.utc.utcoffset(dt):
                    raise ReceiptError("non-UTC timestamp")
            except ValueError as exc:
                raise ReceiptError("invalid UTC timestamp") from exc
    if "environment" in build:
        env = build["environment"]
        if not isinstance(env, dict) or set(env) - {"machine","java","android_sdk","gradle"} or any(
            not isinstance(v, str) or len(v) > 100 for v in env.values()
        ):
            raise ReceiptError("invalid environment metadata")
    artifact = build.get("artifact")
    if not isinstance(artifact, dict) or set(artifact) != {
        "filename", "bytes", "sha256_claimed"
    }:
        raise ReceiptError("artifact requires filename, byte count and claimed digest")
    name, size, digest = artifact["filename"], artifact["bytes"], artifact["sha256_claimed"]
    if not isinstance(name, str) or not APK_NAME.fullmatch(name):
        raise ReceiptError("invalid APK filename")
    if type(size) is not int or size < 1:
        raise ReceiptError("invalid APK byte count")
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        raise ReceiptError("invalid claimed SHA-256")
    # Strict root/build and artifact fields disallow keys and tokens. Optional non-artifact
    # fields are not used as proof: they may be claims from an untrusted JSON file.
    return artifact


def load_receipt(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ReceiptError("receipt is unavailable, linked, or too large")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptError("receipt is not valid UTF-8 JSON") from exc


def compare_apk(apk: Path, receipt: object) -> dict:
    artifact = validate_receipt(receipt)
    if apk.is_symlink() or not apk.is_file() or not stat.S_ISREG(apk.stat().st_mode):
        raise ReceiptError("APK must be an existing regular file, not a symlink")
    before = apk.stat()
    if apk.name != artifact["filename"]:
        raise ReceiptError("APK basename does not match receipt")
    sha = hashlib.sha256()
    bytes_read = 0
    with apk.open("rb") as inp:
        while True:
            chunk = inp.read(CHUNK_BYTES)
            if not chunk:
                break
            sha.update(chunk)
            bytes_read += len(chunk)
    after = apk.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ) or bytes_read != before.st_size:
        raise ReceiptError("APK changed while being hashed; re-read stable bytes")
    observed = sha.hexdigest()
    size_match = bytes_read == artifact["bytes"]
    digest_match = hmac.compare_digest(observed, artifact["sha256_claimed"].lower())
    return {
        "source_attestation": "UNVERIFIED_USER_SUPPLIED",
        "apk_filename": apk.name,
        "bytes_computed": bytes_read,
        "sha256_computed": observed,
        "byte_count_matches_claim": size_match,
        "digest_matches_claim": digest_match,
        "outcome": "LOCAL_BYTES_MATCH_CLAIM" if size_match and digest_match else "MISMATCH",
        "provider_authenticated": False,
        "apk_install_tested": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Offline read-only APK to claimed receipt comparison")
    p.add_argument("--apk", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args()
    try:
        result = compare_apk(args.apk, load_receipt(args.receipt))
    except (OSError, ReceiptError) as exc:
        print(json.dumps({"outcome": "ERROR", "error": str(exc), "verified": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "LOCAL_BYTES_MATCH_CLAIM" else 1


if __name__ == "__main__":
    raise SystemExit(main())
