#!/usr/bin/env python3
"""EchoCopy: local, bounded, read-only SelmaOS PR monitor for Android/Linux.

Runs only when the owner starts it. This is NOT a separate AI identity, a
continuous cloud agent, or proof of Android APK/CI acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time

REPO = "Spiritjcrow/Selma.0"
PR = 50
EXPECTED = "5bd56808da6977f5510a002062c9157bb8fa61b8"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ROLE = "EchoCopy local virtual monitoring worker (not independent White identity)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_dir(arg: str | None) -> Path:
    return Path(arg).expanduser() if arg else Path.home() / ".selma" / "echocopy"


def connect(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(root / "events.sqlite3", timeout=8)
    con.execute("PRAGMA busy_timeout=8000")
    con.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at TEXT NOT NULL, result TEXT NOT NULL, head_sha TEXT, note TEXT NOT NULL)")
    con.commit()
    return con


def query_pr(timeout=20) -> tuple[str, str, str]:
    """Only one hard-coded read-only GitHub REST endpoint is permitted."""
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{REPO}/pulls/{PR}", "--jq", ".head.sha"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=timeout, check=False,
        )
    except FileNotFoundError:
        return "BLOCKED", "", "gh CLI is not installed"
    except subprocess.TimeoutExpired:
        return "BLOCKED", "", "GitHub read timed out"
    if proc.returncode:
        return "BLOCKED", "", "GitHub access or network unavailable"
    sha = proc.stdout.strip()
    if not SHA_RE.fullmatch(sha):
        return "BLOCKED", "", "GitHub response is not a commit SHA"
    if sha == EXPECTED:
        return "UNCHANGED", sha, "PR head matches pinned QA commit"
    return "CHANGED", sha, "PR head changed; revalidate before using old QA evidence"


def record(con: sqlite3.Connection, result: str, sha: str, note: str) -> dict:
    t = now()
    con.execute("INSERT INTO events(at,result,head_sha,note) VALUES (?,?,?,?)", (t, result, sha, note))
    con.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 500)")
    con.commit()
    return {"at": t, "role": ROLE, "repository": REPO, "pr": PR,
            "expected_sha": EXPECTED, "head_sha": sha or None,
            "result": result, "note": note, "apk_verified": False,
            "independent_tester_verified": False, "ci_verified": False}


def last_status(con: sqlite3.Connection) -> dict:
    row = con.execute("SELECT at,result,head_sha,note FROM events ORDER BY id DESC LIMIT 1").fetchone()
    count = con.execute("SELECT count(*) FROM events").fetchone()[0]
    return {"instance": "EchoCopy", "role": ROLE, "checks_recorded": count,
            "last_check_utc": row[0] if row else None,
            "last_result": row[1] if row else "NOT_RUN",
            "last_head_sha": row[2] if row else None,
            "last_note": row[3] if row else "No GitHub check has run",
            "independent_tester_verified": False,
            "apk_verified": False, "ci_verified": False}


def write_report(path: str | None, payload: dict) -> None:
    if not path:
        return
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + f".{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def check(root: Path, report: str | None) -> dict:
    with connect(root) as con:
        result, sha, note = query_pr()
        item = record(con, result, sha, note)
    write_report(report, item)
    return item


def run(args) -> int:
    root = state_dir(args.state_dir)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "worker.lock", "a+b") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("BLOCKED: another EchoCopy worker already owns the lock")
            return 2
        stop = root / "STOP"
        if stop.exists():
            print("BLOCKED: stop flag is set; run 'resume' first")
            return 2
        (root / "worker.pid").write_text(str(os.getpid()) + "\n", encoding="utf-8")
        try:
            print(f"ECHOCOPY STARTED PID={os.getpid()} UTC={now()}", flush=True)
            while not stop.exists():
                result = check(root, args.report)
                print(json.dumps(result, sort_keys=True), flush=True)
                if args.once:
                    break
                # Frequent stop checks; network polling only every interval.
                for _ in range(args.interval):
                    if stop.exists():
                        break
                    time.sleep(1)
        finally:
            (root / "worker.pid").unlink(missing_ok=True)
            print("ECHOCOPY STOPPED", flush=True)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["run", "once", "status", "stop", "resume"])
    p.add_argument("--state-dir")
    p.add_argument("--interval", type=int, default=300)
    p.add_argument("--report", help="optional SD-card JSON status export")
    args = p.parse_args(argv)
    if not 60 <= args.interval <= 86400:
        p.error("--interval must be between 60 and 86400 seconds")
    root = state_dir(args.state_dir)
    if args.action == "stop":
        root.mkdir(parents=True, exist_ok=True)
        (root / "STOP").write_text("operator requested stop\n", encoding="utf-8")
        print("STOP REQUESTED: worker exits after its current bounded check")
        return 0
    if args.action == "resume":
        (root / "STOP").unlink(missing_ok=True)
        print("STOP CLEARED: use run to start the worker")
        return 0
    if args.action == "status":
        with connect(root) as con:
            print(json.dumps(last_status(con), indent=2, sort_keys=True))
        return 0
    args.once = args.action == "once"
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
