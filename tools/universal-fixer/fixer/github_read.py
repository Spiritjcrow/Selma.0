"""Read-only GitHub REST inventory with explicit pagination and no synthetic data."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request

class GitHubError(RuntimeError):pass

class GitHubReadOnly:
    def __init__(self, token=None, timeout=12, max_pages=20):
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self.timeout = timeout
        self.max_pages = max_pages

    def _get(self, url):
        headers = {"Accept":"application/vnd.github+json", "User-Agent":"Selma-Fixer-Read-Only/0.1", "X-GitHub-Api-Version":"2022-11-28"}
        if self.token:headers["Authorization"]="Bearer "+self.token
        req=urllib.request.Request(url,headers=headers,method="GET")
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as response:
                result=json.load(response)
                if not isinstance(result,list):raise GitHubError("Expected a JSON list")
                return result
        except urllib.error.HTTPError as e:
            raise GitHubError(f"GitHub HTTP {e.code}; check permission, rate limits, repo visibility") from None
        except (urllib.error.URLError,TimeoutError,ValueError) as e:
            raise GitHubError(f"GitHub unavailable/invalid response: {type(e).__name__}") from None

    def pages(self, repo, endpoint):
        if not repo or repo.count("/")!=1 or endpoint not in ("issues","pulls"):
            raise ValueError("Invalid repository/endpoint")
        owner,name=repo.split("/")
        if not all(all(c.isalpha() or c.isdigit() or c in "-_." for c in part) for part in (owner,name)):
            raise ValueError("Invalid repository characters")
        records=[]
        for page in range(1,self.max_pages+1):
            url=f"https://api.github.com/repos/{owner}/{name}/{endpoint}?state=open&per_page=100&page={page}"
            batch=self._get(url)
            records.extend(batch)
            if len(batch)<100:return records
        raise GitHubError(f"Pagination incomplete for {repo}/{endpoint}; max_pages={self.max_pages}")

    def inventory_repo(self, repo):
        # GitHub Issues API includes pull requests: exclude objects with pull_request.
        issues=[{"repository":repo,"kind":"issue","number":x["number"],"title":x["title"],"url":x["html_url"],"updated_at":x.get("updated_at"),"head_sha":None}
                for x in self.pages(repo,"issues") if "pull_request" not in x]
        prs=[{"repository":repo,"kind":"pr","number":x["number"],"title":x["title"],"url":x["html_url"],"updated_at":x.get("updated_at"),"head_sha":(x.get("head") or {}).get("sha")}
             for x in self.pages(repo,"pulls")]
        return issues+prs