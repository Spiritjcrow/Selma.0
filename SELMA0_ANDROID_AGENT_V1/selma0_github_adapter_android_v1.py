#!/usr/bin/env python3
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


_GITHUB_API_HOST_V1 = "api.github.com"
_GITHUB_API_BASE_V1 = "https://api.github.com"
_GITHUB_API_VERSION_V1 = "2026-03-10"
_MAX_RESPONSE_BYTES_V1 = 2 * 1024 * 1024
_DEFAULT_TIMEOUT_SECONDS_V1 = 15
_REPO_PART_V1 = re.compile(r"^[A-Za-z0-9_.-]+$")


class _NoRedirectHandlerV1(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _validate_repo_spec_v1(repo_spec):
    repo_spec = str(repo_spec or "").strip()
    parts = repo_spec.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("GitHub repo must be configured as owner/repo")
    owner, repo = parts
    if len(owner) > 100 or len(repo) > 100:
        raise ValueError("GitHub owner/repo is too long")
    if not _REPO_PART_V1.fullmatch(owner) or not _REPO_PART_V1.fullmatch(repo):
        raise ValueError("GitHub owner/repo contains unsupported characters")
    return owner, repo


def _bounded_json_body_v1(response):
    body = response.read(_MAX_RESPONSE_BYTES_V1 + 1)
    if len(body) > _MAX_RESPONSE_BYTES_V1:
        raise RuntimeError("GitHub API response exceeded size limit")
    try:
        return json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("GitHub API returned invalid JSON") from exc


class Selma0GitHubAdapterAndroidV1:
    """Least-privilege GitHub.com REST adapter for one allowlisted repository.

    Credentials are read from environment variables at request time and are never
    accepted as command arguments or returned by status(). The API hostname is
    fixed to api.github.com, and redirects are refused.
    """

    def __init__(
        self,
        repo_spec=None,
        token_env="SELMA0_GITHUB_TOKEN_V1",
        opener=None,
        timeout_seconds=_DEFAULT_TIMEOUT_SECONDS_V1,
    ):
        self.repo_spec = str(
            repo_spec if repo_spec is not None else os.getenv("SELMA0_GITHUB_REPO_V1", "")
        ).strip()
        self.token_env = str(token_env or "SELMA0_GITHUB_TOKEN_V1")
        self.timeout_seconds = max(1, min(int(timeout_seconds), 60))
        self._opener = opener or urllib.request.build_opener(_NoRedirectHandlerV1())

    def _repo_v1(self):
        if not self.repo_spec:
            raise RuntimeError("SELMA0_GITHUB_REPO_V1 is not configured")
        return _validate_repo_spec_v1(self.repo_spec)

    def _token_v1(self):
        return str(os.getenv(self.token_env, "") or "").strip()

    def status(self):
        repo_valid = False
        repo_error = None
        if self.repo_spec:
            try:
                _validate_repo_spec_v1(self.repo_spec)
                repo_valid = True
            except ValueError as exc:
                repo_error = str(exc)
        token_configured = bool(self._token_v1())
        return {
            "provider": "github",
            "api_host": _GITHUB_API_HOST_V1,
            "api_version": _GITHUB_API_VERSION_V1,
            "repository": self.repo_spec if repo_valid else None,
            "repository_configured": repo_valid,
            "read_configured": repo_valid,
            "write_configured": repo_valid and token_configured,
            "credential_configured": token_configured,
            "credential_exposed": False,
            "configuration_error": repo_error,
            "capabilities": ["repo_summary", "list_issues", "create_issue"],
        }

    def _url_v1(self, suffix="", query=None):
        owner, repo = self._repo_v1()
        owner_q = urllib.parse.quote(owner, safe="")
        repo_q = urllib.parse.quote(repo, safe="")
        url = f"{_GITHUB_API_BASE_V1}/repos/{owner_q}/{repo_q}{suffix}"
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != _GITHUB_API_HOST_V1:
            raise RuntimeError("GitHub adapter URL escaped fixed HTTPS API host")
        return url

    def _request_v1(self, method, suffix="", query=None, payload=None, require_token=False):
        method = str(method or "GET").upper()
        if method not in {"GET", "POST"}:
            raise ValueError("unsupported GitHub HTTP method")
        token = self._token_v1()
        if require_token and not token:
            raise RuntimeError(f"{self.token_env} is required for GitHub write operations")

        body = None
        if payload is not None:
            try:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ValueError("GitHub request payload must be JSON serializable") from exc
            if len(body) > 128 * 1024:
                raise ValueError("GitHub request payload is too large")

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _GITHUB_API_VERSION_V1,
            "User-Agent": "Selma0-Android-Agent-V1",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            self._url_v1(suffix=suffix, query=query),
            data=body,
            headers=headers,
            method=method,
        )
        try:
            response = self._opener.open(request, timeout=self.timeout_seconds)
            with response:
                return _bounded_json_body_v1(response)
        except urllib.error.HTTPError as exc:
            message = f"GitHub API request failed with HTTP {exc.code}"
            try:
                error_body = exc.read(64 * 1024)
                parsed = json.loads(error_body.decode("utf-8")) if error_body else {}
                if isinstance(parsed, dict) and parsed.get("message"):
                    message += f": {str(parsed['message'])[:500]}"
            except Exception:
                pass
            raise RuntimeError(message) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub API connection failed: {str(exc.reason)[:500]}") from exc
        except TimeoutError as exc:
            raise RuntimeError("GitHub API request timed out") from exc

    def repo_summary(self):
        data = self._request_v1("GET")
        if not isinstance(data, dict):
            raise RuntimeError("GitHub repository response must be an object")
        return {
            "ok": True,
            "provider": "github",
            "repository": data.get("full_name"),
            "private": bool(data.get("private")),
            "archived": bool(data.get("archived")),
            "disabled": bool(data.get("disabled")),
            "default_branch": data.get("default_branch"),
            "open_issues_count": data.get("open_issues_count"),
            "updated_at": data.get("updated_at"),
            "html_url": data.get("html_url"),
        }

    def list_issues(self, state="open", limit=20):
        state = str(state or "open").lower()
        if state not in {"open", "closed", "all"}:
            raise ValueError("issue state must be open, closed, or all")
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("issue limit must be an integer") from exc
        limit = max(1, min(limit, 100))
        data = self._request_v1(
            "GET",
            suffix="/issues",
            query={"state": state, "per_page": limit, "sort": "updated", "direction": "desc"},
        )
        if not isinstance(data, list):
            raise RuntimeError("GitHub issues response must be an array")
        issues = []
        for item in data:
            if not isinstance(item, dict) or "pull_request" in item:
                continue
            labels = item.get("labels") if isinstance(item.get("labels"), list) else []
            issues.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "labels": [
                        label.get("name") for label in labels if isinstance(label, dict) and label.get("name")
                    ],
                    "updated_at": item.get("updated_at"),
                    "html_url": item.get("html_url"),
                }
            )
        return {
            "ok": True,
            "provider": "github",
            "repository": self.repo_spec,
            "issue_count": len(issues),
            "issues": issues,
        }

    def create_issue(self, title, body="", labels=None):
        title = str(title or "").strip()
        body = str(body or "")
        if not title:
            raise ValueError("issue title is required")
        if len(title) > 256:
            raise ValueError("issue title is too long")
        if len(body) > 60_000:
            raise ValueError("issue body is too long")
        labels = [] if labels is None else labels
        if not isinstance(labels, list):
            raise ValueError("issue labels must be an array")
        if len(labels) > 20:
            raise ValueError("too many issue labels")
        clean_labels = []
        for label in labels:
            label = str(label or "").strip()
            if not label or len(label) > 100:
                raise ValueError("issue label is empty or too long")
            clean_labels.append(label)
        data = self._request_v1(
            "POST",
            suffix="/issues",
            payload={"title": title, "body": body, "labels": clean_labels},
            require_token=True,
        )
        if not isinstance(data, dict):
            raise RuntimeError("GitHub create-issue response must be an object")
        return {
            "ok": True,
            "provider": "github",
            "repository": self.repo_spec,
            "number": data.get("number"),
            "title": data.get("title"),
            "state": data.get("state"),
            "html_url": data.get("html_url"),
            "created_at": data.get("created_at"),
        }


def register_github_adapter_tools(tool_registry, plugin_registry=None, adapter=None):
    adapter = adapter or Selma0GitHubAdapterAndroidV1()
    if plugin_registry is not None:
        plugin_registry.register("github", adapter)
    tool_registry.register(
        "github.repo_summary",
        lambda: adapter.repo_summary(),
        risk="sensitive_read",
        description="Read summary metadata for the single configured GitHub repository.",
    )
    tool_registry.register(
        "github.list_issues",
        lambda state="open", limit=20: adapter.list_issues(state=state, limit=limit),
        risk="sensitive_read",
        description="List issues from the single configured GitHub repository.",
    )
    tool_registry.register(
        "github.create_issue",
        lambda title="", body="", labels=None: adapter.create_issue(title=title, body=body, labels=labels),
        risk="external_effect",
        description="Create an issue in the configured GitHub repository; explicit approval required.",
    )
    return adapter
