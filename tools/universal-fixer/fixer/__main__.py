"""CLI: Python 3.10+, stdlib only. No unauthorized network writes or shell execution."""
import argparse
import ast
import hashlib
import json
import os
import sys
from pathlib import Path
from .core import CHOICES, Registry
from .github_read import GitHubReadOnly,GitHubError
from .reporting import generate
from .repair import RepairError, load_plan, preflight, execute, make_plan, validate_plan

def db_default():
    base=Path(os.getenv("APPDATA") or os.getenv("XDG_DATA_HOME") or Path.home()/".local"/"share")
    return str(base/"selma-fixer"/"registry.sqlite3")

def main():
    parser=argparse.ArgumentParser(prog="python -m fixer",description="Evidence-first developer-work inventory and safe isolated local repair runner")
    parser.add_argument("--db",default=db_default(),help="Local SQLite file path (never commit this file)")
    sub=parser.add_subparsers(dest="command",required=True)
    a=sub.add_parser("sync",help="Read actual GitHub issue/PR inventory (no writes)");a.add_argument("--repos",default="config/repositories.json")
    a=sub.add_parser("import",help="Import a reviewed source snapshot (must contain real records)");a.add_argument("path")
    a=sub.add_parser("report",help="Generate browseable HTML, JSON and Markdown");a.add_argument("--output",default="output")
    sub.add_parser("queue",help="Show prioritised unverified items")
    a=sub.add_parser("decide",help="Record A/B/C/D read-only review decision");a.add_argument("key");a.add_argument("choice",choices=sorted(CHOICES.keys()))
    a=sub.add_parser("check",help="Static AST syntax check of an explicitly selected local source tree");a.add_argument("source")
    sub.add_parser("audit",help="Verify local audit-chain hash consistency")
    a=sub.add_parser("repair-plan",help="Validate an exact proposed patch against an owned local Git checkout")
    a.add_argument("--repo",required=True);a.add_argument("--plan",required=True)
    a=sub.add_parser("repair-run",help="Reproduce RED -> patch -> prove GREEN -> commit on an isolated local branch")
    a.add_argument("--repo",required=True);a.add_argument("--plan",required=True)
    a.add_argument("--approve-digest",required=True,help="Exact digest shown at repair-plan; approvals are source-bound")
    a.add_argument("--evidence",required=True,help="Write-once local JSON evidence record")
    a.add_argument("--timeout",type=int,default=120)
    args=parser.parse_args()
    if args.command in ("repair-plan","repair-run"):
        plan,digest=load_plan(args.plan)
        root,head=preflight(args.repo,plan)
        if args.command=="repair-plan":
            print(json.dumps({"status":"READY_FOR_EXPLICIT_LOCAL_APPROVAL","task_id":plan["task_id"],
                              "base_sha":head,"plan_sha256":digest,"target":plan["change"]["path"],
                              "tests":plan["tests"],"effect":"local worktree and commit only; no push/merge/deploy"},indent=2))
            return 0
        if not 1<=args.timeout<=1800:parser.error("timeout must be 1..1800 seconds")
        r=execute(root,plan,args.approve_digest,args.evidence,timeout=args.timeout)
        print(json.dumps(r,indent=2))
        return 0 if r["status"]=="LOCAL_COMMIT_TESTED" else 4
    if args.command=="check":
        root=Path(args.source).resolve()
        if not root.is_dir():parser.error("Source must be an existing directory")
        files=sorted(p for p in root.rglob("*.py") if not p.is_symlink() and not any(x in (".git","venv",".venv") for x in p.parts))
        if not files:parser.error("No Python files found; cannot report PASS")
        errors=[];h=hashlib.sha256()
        for f in files:
            try:
                data=f.read_bytes();ast.parse(data.decode("utf-8-sig"),filename=f.name);h.update(f.relative_to(root).as_posix().encode()+b"\0"+data)
            except (SyntaxError,UnicodeError,OSError,ValueError) as e:errors.append(f"{f.name}: {e}")
        print(json.dumps({"check":"syntax_only","python_files":len(files),"errors":errors,"evidence_sha256":h.hexdigest(),"code_executed":False},indent=2))
        return 1 if errors else 0
    with Registry(args.db) as reg:
        if args.command=="sync":
            repos=json.loads(Path(args.repos).read_text(encoding="utf8"))
            if not isinstance(repos,list) or not repos:parser.error("Repos JSON must be a nonempty array of owner/name strings")
            client=GitHubReadOnly();errors=[];total=0
            for repo in repos:
                try:
                    records=client.inventory_repo(repo)
                    for item in records:reg.import_item(item)
                    total+=len(records)
                    print(f"{repo}: imported {len(records)} actual open tracking records")
                except (GitHubError,ValueError,KeyError) as e:
                    errors.append(f"{repo}: {e}")
            if errors:
                print("INCOMPLETE inventory; unresolved sources:\n"+"\n".join(errors),file=sys.stderr)
                return 2
            print(f"Completed read-only GitHub snapshot: {total} open items; no source tests executed")
        elif args.command=="import":
            payload=json.loads(Path(args.path).read_text(encoding="utf8"))
            records=payload["items"] if isinstance(payload,dict) else payload
            if not isinstance(records,list):parser.error("Snapshot must be a list or items list")
            for item in records:reg.import_item(item,provenance="explicit_snapshot_import")
            print(f"Imported {len(records)} records; provenance=explicit_snapshot_import (not freshly queried)")
        elif args.command=="report":
            print(f"Wrote {generate(reg,args.output)} items to {args.output}/ (HTML, JSON, Markdown)")
        elif args.command=="queue":
            for x in reg.list_items():
                print(f"{x['priority']} {x['item_key']} [{x['decision'] or 'UNREVIEWED'}] {x['title'][:90]}")
            if not reg.list_items():print("NO SOURCE ITEMS: run sync with authorized GitHub access or import a real snapshot")
        elif args.command=="decide":
            print("Recorded decision:",reg.decide(args.key,args.choice),"— no external operations executed")
        elif args.command=="audit":
            ok=reg.verify_chain();print("Local audit hash chain:","PASS" if ok else "FAIL");return 0 if ok else 3
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except (RepairError,ValueError,FileNotFoundError,KeyError,json.JSONDecodeError) as e:
        print("INPUT ERROR:",e,file=sys.stderr);sys.exit(2)