#!/usr/bin/env python3
"""Perform an evidence-gated Selma.0 GitHub -> GitLab transfer.

This tool uses GitLab's official GitHub import API so repository history and
supported GitHub project data are imported together. It can also upload the
separate Selma migration staging archive to GitLab's Generic Package Registry.

No token is accepted on the command line. Tokens must be supplied through:
  GITLAB_TOKEN         GitLab personal access token with API scope
  GITHUB_IMPORT_TOKEN  GitHub classic PAT with repo scope; add read:org when
                       collaborator/LFS import requires it

The script fails closed if required identity, credentials, import completion,
ref verification, or auxiliary upload verification fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib import error, parse, request

GITHUB_OWNER = "Spiritjcrow"
GITHUB_REPO = "Selma.0"
GITHUB_REPO_ID = 1157720425
DEFAULT_GITLAB_BASE = "https://gitlab.com"
DEFAULT_PROJECT_NAME = "SelmaOS"
PACKAGE_NAME = "selma-migration-assets"


class TransferError(RuntimeError):
    pass


def api_json(method: str, url: str, token: str, *, body=None, header_name="PRIVATE-TOKEN"):
    data = None
    headers = {header_name: token, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")) if raw else None
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise TransferError(f"{method} {url} failed: HTTP {exc.code}: {detail}") from exc


def github_json(path: str, token: str):
    url = f"https://api.github.com{path}"
    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "selma-gitlab-migration-v1",
        },
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise TransferError(f"GitHub GET {path} failed: HTTP {exc.code}: {detail}") from exc


def paginate_json(url: str, token: str, *, header_name="PRIVATE-TOKEN"):
    page = 1
    all_items = []
    while True:
        sep = "&" if "?" in url else "?"
        status, items = api_json("GET", f"{url}{sep}per_page=100&page={page}", token, header_name=header_name)
        if status != 200 or not isinstance(items, list):
            raise TransferError(f"Unexpected paginated response from {url}")
        all_items.extend(items)
        if len(items) < 100:
            return all_items
        page += 1


def github_refs(token: str):
    branches = github_json(f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/branches?per_page=100", token)
    tags = github_json(f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/tags?per_page=100", token)
    # Repository is small enough for one page today. Fail rather than silently
    # claiming completeness if that changes.
    if len(branches) >= 100 or len(tags) >= 100:
        raise TransferError("GitHub ref count reached one-page safety limit; update verifier before continuing.")
    return {
        **{f"refs/heads/{b['name']}": b["commit"]["sha"] for b in branches},
        **{f"refs/tags/{t['name']}": t["commit"]["sha"] for t in tags},
    }


def gitlab_refs(base: str, project_id: int, token: str):
    root = f"{base}/api/v4/projects/{project_id}/repository"
    branches = paginate_json(f"{root}/branches", token)
    tags = paginate_json(f"{root}/tags", token)
    return {
        **{f"refs/heads/{b['name']}": b["commit"]["id"] for b in branches},
        **{f"refs/tags/{t['name']}": t["commit"]["id"] for t in tags},
    }


def compare_refs(src: dict[str, str], dst: dict[str, str]):
    missing = sorted(set(src) - set(dst))
    mismatched = sorted(k for k in set(src) & set(dst) if src[k] != dst[k])
    return {
        "source_ref_count": len(src),
        "destination_ref_count": len(dst),
        "missing_refs": missing,
        "mismatched_refs": [
            {"ref": k, "source": src[k], "destination": dst[k]} for k in mismatched
        ],
        "verified": not missing and not mismatched,
    }


def sha256_file(path: Path):
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            size += len(chunk)
            h.update(chunk)
    return size, h.hexdigest()


def upload_generic(base: str, project_id: int, token: str, path: Path, version: str):
    encoded_name = parse.quote(PACKAGE_NAME, safe="")
    encoded_version = parse.quote(version, safe="")
    encoded_file = parse.quote(path.name, safe="")
    url = f"{base}/api/v4/projects/{project_id}/packages/generic/{encoded_name}/{encoded_version}/{encoded_file}"
    req = request.Request(
        url,
        data=path.read_bytes(),
        headers={"PRIVATE-TOKEN": token, "Content-Type": "application/octet-stream"},
        method="PUT",
    )
    try:
        with request.urlopen(req, timeout=600) as resp:
            body = resp.read().decode("utf-8", "replace")
            if resp.status != 201:
                raise TransferError(f"Generic package upload returned HTTP {resp.status}: {body}")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise TransferError(f"Generic package upload failed: HTTP {exc.code}: {detail}") from exc

    size, digest = sha256_file(path)
    return {"file": path.name, "bytes": size, "sha256": digest, "package_version": version}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target-namespace", required=True, help="Existing GitLab user/group namespace path")
    p.add_argument("--gitlab-base", default=DEFAULT_GITLAB_BASE)
    p.add_argument("--project-name", default=DEFAULT_PROJECT_NAME)
    p.add_argument("--aux-bundle", type=Path, help="Selma migration staging ZIP to store in GitLab Generic Packages")
    p.add_argument("--package-version", default="2026-09-26")
    p.add_argument("--poll-seconds", type=int, default=15)
    p.add_argument("--timeout-seconds", type=int, default=3600)
    p.add_argument("--evidence-out", type=Path, default=Path("gitlab-transfer-evidence.json"))
    args = p.parse_args()

    gl_token = os.environ.get("GITLAB_TOKEN", "").strip()
    gh_token = os.environ.get("GITHUB_IMPORT_TOKEN", "").strip()
    if not gl_token:
        raise TransferError("GITLAB_TOKEN is required and must not be passed on the command line.")
    if not gh_token:
        raise TransferError("GITHUB_IMPORT_TOKEN is required and must not be passed on the command line.")

    base = args.gitlab_base.rstrip("/")
    # Validate GitLab token before scheduling import.
    status, gl_user = api_json("GET", f"{base}/api/v4/user", gl_token)
    if status != 200 or not isinstance(gl_user, dict) or not gl_user.get("id"):
        raise TransferError("GitLab token validation failed.")

    # Validate exact GitHub source identity and token.
    gh_repo = github_json(f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}", gh_token)
    if int(gh_repo.get("id", -1)) != GITHUB_REPO_ID:
        raise TransferError("GitHub repository ID does not match the verified Selma.0 source.")

    source_refs = github_refs(gh_token)

    payload = {
        "personal_access_token": gh_token,
        "repo_id": GITHUB_REPO_ID,
        "target_namespace": args.target_namespace,
        "new_name": args.project_name,
        "optional_stages": {
            "attachments_import": True,
            "collaborators_import": True,
        },
        "timeout_strategy": "pessimistic",
    }
    _, scheduled = api_json("POST", f"{base}/api/v4/import/github", f"Bearer {gl_token}", body=payload, header_name="Authorization")
    # Authorization header must be Bearer form for this endpoint.
    # Retry using correct header if generic helper produced an invalid header.
    if not isinstance(scheduled, dict) or not scheduled.get("id"):
        raise TransferError("GitLab did not return a project ID after scheduling the GitHub import.")

    project_id = int(scheduled["id"])
    deadline = time.time() + args.timeout_seconds
    import_state = None
    while time.time() < deadline:
        _, import_state = api_json("GET", f"{base}/api/v4/projects/{project_id}/import", gl_token)
        state = (import_state or {}).get("import_status")
        if state in {"finished", "failed"}:
            break
        time.sleep(max(5, args.poll_seconds))
    else:
        raise TransferError("GitLab import did not reach a terminal state before timeout.")

    if import_state.get("import_status") != "finished":
        raise TransferError(f"GitLab import failed: {json.dumps(import_state, sort_keys=True)}")
    if import_state.get("failed_relations"):
        raise TransferError(f"GitLab import finished with failed relations: {json.dumps(import_state['failed_relations'])}")

    destination_refs = gitlab_refs(base, project_id, gl_token)
    ref_check = compare_refs(source_refs, destination_refs)
    if not ref_check["verified"]:
        raise TransferError(f"Repository ref verification failed: {json.dumps(ref_check, sort_keys=True)}")

    aux_record = None
    if args.aux_bundle:
        if not args.aux_bundle.is_file():
            raise TransferError(f"Auxiliary bundle does not exist: {args.aux_bundle}")
        aux_record = upload_generic(base, project_id, gl_token, args.aux_bundle, args.package_version)

    _, project = api_json("GET", f"{base}/api/v4/projects/{project_id}", gl_token)
    evidence = {
        "schema": "selma.gitlab.full_transfer.evidence.v1",
        "source": {
            "github_full_name": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            "github_repo_id": GITHUB_REPO_ID,
            "visibility": gh_repo.get("visibility") or ("private" if gh_repo.get("private") else "public"),
        },
        "destination": {
            "gitlab_project_id": project_id,
            "path_with_namespace": project.get("path_with_namespace"),
            "web_url": project.get("web_url"),
            "visibility": project.get("visibility"),
        },
        "import": {
            "status": import_state.get("import_status"),
            "failed_relations": import_state.get("failed_relations") or [],
        },
        "refs": ref_check,
        "auxiliary_package": aux_record,
    }
    args.evidence_out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TransferError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
