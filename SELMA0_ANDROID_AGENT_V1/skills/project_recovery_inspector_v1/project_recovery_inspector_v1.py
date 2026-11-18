#!/usr/bin/env python3
import csv, hashlib, json, os, re
from pathlib import Path

VERSION="1.0.0"
SKIP={".git",".gradle","node_modules","build","dist",".venv","venv","__pycache__","target"}
TEXT={".txt",".md",".rst",".json",".jsonl",".yaml",".yml",".toml",".ini",".cfg",".py",".sh",".java",".kt",".kts",".gradle",".xml",".html",".css",".js",".ts",".tsx",".jsx",".c",".h",".cpp",".hpp",".cs",".go",".rs",".swift",".sql",".properties"}

REMEDIATIONS={
"ci_admission":(100,"Restore the CI control plane, then rerun unchanged code.",[
"Verify repository/account/organization Actions enablement and policy.",
"Verify private-repository Actions quota, spending/billing state, and hosted-runner eligibility.",
"Use a zero-dependency one-job probe; if it still dies before job creation, stop patching application code.",
"After admission is restored, rerun the original workflow and record the first real job result.",
"Escalate to the hosting provider with run IDs if admission still fails before jobs exist."]),
"failing_test":(95,"Reduce the failure to one reproducible contract violation, repair it, and keep the regression test.",[
"Run only the first failing test with deterministic inputs.","Capture assertion, fixture, environment, and dependency versions.","Repair the invariant or implementation rather than weakening a valid test."]),
"permission_or_policy":(92,"Correct the controlling permission or policy instead of creating a bypass path.",[
"Identify whether the authority is app, OS, repository, account, or external service.","Expose the exact denial and legitimate action required.","Retest the unchanged operation after permission is corrected."]),
"stale_branch":(88,"Port the still-valid slice onto current main instead of merging stale architecture wholesale.",[
"Compare the stale branch with current main.","Move only unique valid work to a clean current branch.","Keep all external effects behind the current command/permission/audit plane."]),
"dependency_or_environment":(84,"Make the environment deterministic and fail early with exact missing prerequisites.",[
"Pin runtime/compiler/SDK/package versions.","Separate install failures from application failures.","Add a preflight that reports the exact missing prerequisite."]),
"missing_implementation":(80,"Turn the unmet requirement into an executable contract and implement the smallest truthful vertical slice.",[
"Translate the requirement into a test or contract.","Implement explicit degraded-state behavior.","Do not claim hardware/network/deployment behavior without direct evidence."]),
"unverified_acceptance":(72,"Close the evidence gap without modifying working code.",[
"Identify which acceptance item lacks evidence.","Run the exact validation on the required platform/device.","Record versions, output, artifact hash, and pass/fail state."]),
"external_gate":(86,"Make the external dependency first-class so it cannot masquerade as an internal code defect.",[
"Record dependency, owner, evidence, and resume condition.","Continue independent work without falsifying completion.","Re-evaluate when new evidence arrives."]),
"hold_marker":(60,"Replace vague waiting state with a typed prerequisite and proof condition.",[
"Read the surrounding evidence to identify the prerequisite.","Classify it as code, evidence, permission, hardware, dependency, or external service.","Remove the hold only when the condition is evidenced."])
}
RULES=[
("ci_admission",r"\b(startup_failure|BuildFailed|No jobs were run|zero jobs|before (?:any )?job)\b","critical"),
("failing_test",r"\b(?:FAILED|FAILURES?|ERRORS?)\b|\b\d+\s+failed\b","high"),
("permission_or_policy",r"\b(permission denied|forbidden|403\b|policy block|administrator|requires approval|not authorized)\b","high"),
("stale_branch",r"\b(stale branch|do not merge .*as-is|rebase/port|retarget .* main)\b","high"),
("dependency_or_environment",r"\b(module not found|command not found|missing dependency|missing executable|version mismatch|dependency conflict)\b","high"),
("missing_implementation",r"\b(not implemented|incomplete|missing implementation|TODO\b|FIXME\b)\b","medium"),
("unverified_acceptance",r"\b(unverified|not verified|no .* evidence|does not claim|has not claimed|remain(?:s)? .* gate)\b","medium"),
("hold_marker",r"\b(blocked|on hold|waiting for|pending|cannot proceed|must .* before|depends on)\b","medium"),
]
RULES=[(a,re.compile(b,re.I),c) for a,b,c in RULES]
CHECK=re.compile(r"^\s*[-*]\s*\[\s\]\s+(.+)$")

def _p(v): return Path(os.path.expanduser(str(v))).resolve()
def _sha(b): return hashlib.sha256(b).hexdigest()
def _finding(cat,sev,src,line,text,origin="source",extra=None):
    pri,fix,opts=REMEDIATIONS[cat]
    d={"id":_sha(f"{cat}|{src}|{line}|{text.strip()}".encode())[:16],"category":cat,"severity":sev,"source":src,"line":line,"origin":origin,"evidence":text.strip()[:1200],"priority":pri,"native_fix":fix,"possibilities":list(opts)}
    if extra:d.update(extra)
    return d
def _scan(text,src,origin="source"):
    out=[]
    for n,line in enumerate(text.splitlines(),1):
        m=CHECK.match(line)
        if m: out.append(_finding("unverified_acceptance","medium",src,n,"Unchecked acceptance item: "+m.group(1),origin))
        for cat,pat,sev in RULES:
            if pat.search(line): out.append(_finding(cat,sev,src,n,line,origin))
    return out
def _files(root,limit):
    if root.is_file():
        yield root; return
    n=0
    for x in sorted(root.rglob("*")):
        if n>=limit:return
        if not x.is_file() or any(part in SKIP for part in x.parts):continue
        if x.suffix.lower() not in TEXT and x.name not in {"Dockerfile","Makefile","gradlew"}:continue
        yield x;n+=1
def _msg(m):
    if not isinstance(m,dict):return ""
    c=m.get("content")
    if isinstance(c,dict):
        p=c.get("parts")
        if isinstance(p,list):return "\n".join(str(x) for x in p if x is not None)
        if c.get("text") is not None:return str(c["text"])
    if isinstance(c,str):return c
    for k in ("text","body","message"):
        if m.get(k) is not None:return str(m[k])
    return ""
def _chats(path):
    s=path.suffix.lower()
    if s==".json":
        d=json.loads(path.read_text(encoding="utf-8"))
        conv=d if isinstance(d,list) else d.get("conversations") if isinstance(d,dict) else None
        if isinstance(conv,list) and any(isinstance(x,dict) and "mapping" in x for x in conv):
            for i,c in enumerate(conv):
                if not isinstance(c,dict):continue
                title=str(c.get("title") or f"conversation-{i+1}")
                for node_id,node in (c.get("mapping") or {}).items():
                    m=node.get("message") if isinstance(node,dict) else None
                    t=_msg(m).strip()
                    if t:
                        a=m.get("author") or {};role=a.get("role") if isinstance(a,dict) else "unknown"
                        yield title,str(role or "unknown"),str(node_id),t
            return
        for i,x in enumerate(d if isinstance(d,list) else [d]):
            t=_msg(x).strip() if isinstance(x,dict) else str(x)
            if not t and isinstance(x,dict):t=json.dumps(x,ensure_ascii=False)
            if t:yield path.name,"unknown",str(i),t
    elif s==".jsonl":
        for i,line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():continue
            x=json.loads(line);t=_msg(x).strip() if isinstance(x,dict) else str(x)
            if t:yield path.name,"unknown",str(i),t
    elif s==".csv":
        with path.open("r",encoding="utf-8",newline="") as h:
            for i,row in enumerate(csv.DictReader(h)):
                t=next((str(row[k]) for k in ("content","text","message","body") if row.get(k)),"")
                if t:yield path.name,str(row.get("role") or "unknown"),str(i),t
    else:
        for i,line in enumerate(path.read_text(encoding="utf-8",errors="replace").splitlines()):
            if line.strip():yield path.name,"unknown",str(i),line
def _manifest(path):
    p=_p(path);d=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d,dict) or not str(d.get("project_id") or "").strip():raise ValueError("manifest requires project_id")
    return p,d
def inspect_project(manifest_path,source_roots=None,chat_exports=None,max_files=5000,max_bytes_per_file=1048576):
    mf,m=_manifest(manifest_path);roots=list(source_roots or m.get("source_roots") or []);exports=list(chat_exports or [])
    max_files=max(1,min(int(max_files),20000));max_bytes_per_file=max(4096,min(int(max_bytes_per_file),8388608))
    f=[];scanned=[];errors=[];missing=[];chat_count=0
    for rv in roots:
        r=_p(rv)
        if not r.exists():missing.append(str(r));continue
        for x in _files(r,max_files):
            try:
                raw=x.read_bytes();tr=len(raw)>max_bytes_per_file;raw=raw[:max_bytes_per_file];text=raw.decode("utf-8",errors="replace")
                scanned.append({"path":str(x),"sha256_prefix":_sha(raw)[:16],"truncated":tr})
                f+=_scan(text,str(x))
            except Exception as e:errors.append({"source":str(x),"error":str(e)})
    keys=[str(k).lower() for k in m.get("keywords",[]) if str(k).strip()]
    for ev in exports:
        p=_p(ev)
        if not p.exists():missing.append(str(p));continue
        ps=[p] if p.is_file() else list(_files(p,max_files))
        for x in ps:
            if x.suffix.lower() not in {".json",".jsonl",".csv",".txt"}:continue
            try:
                for title,role,node,t in _chats(x):
                    chat_count+=1
                    if keys and not any(k in t.lower() for k in keys):continue
                    f+=_scan(t,f"{x}::{title}::{role}::{node}","chat_export")
            except Exception as e:errors.append({"source":str(x),"error":"chat parse: "+str(e)})
    for g in m.get("known_external_gates",[]):
        if not isinstance(g,dict) or g.get("active") is False:continue
        ev=str(g.get("evidence") or g.get("description") or g.get("id") or "external gate")
        item=_finding("external_gate",str(g.get("severity") or "high"),str(mf),0,ev,"manifest",{
            "priority":int(g.get("priority") or REMEDIATIONS["external_gate"][0]),"external_owner":g.get("owner"),"resume_condition":g.get("resume_condition")})
        if g.get("remediation"):item["possibilities"]=list(g["remediation"])
        f.append(item)
    for src in missing:
        f.append(_finding("external_gate","medium",str(mf),0,f"Configured source is unavailable in this runtime: {src}","runtime",{
            "priority":70,"native_fix":"Mount, export, or materialize the real source instead of substituting mock data.",
            "possibilities":["Provide the real project directory/archive.","Provide a user-authorized chat export when chat history is required.","Materialize the canonical repository/document source."]}))
    seen=set();out=[]
    for x in sorted(f,key=lambda z:(-z["priority"],z["source"],z["line"],z["category"])):
        k=(x["category"],x["source"],x["line"],x["evidence"])
        if k not in seen:seen.add(k);out.append(x)
    counts={}
    for x in out:counts[x["category"]]=counts.get(x["category"],0)+1
    nexts=[];cats=set()
    for x in out:
        if x["category"] in cats:continue
        cats.add(x["category"]);nexts.append({"category":x["category"],"priority":x["priority"],"action":x["native_fix"],"evidence_id":x["id"]})
        if len(nexts)>=5:break
    return {"skill":"project_recovery_inspector_v1","skill_version":VERSION,"project_id":m["project_id"],"project_name":m.get("name",m["project_id"]),
      "truth_policy":{"verified_only":True,"mock_success_allowed":False,"chat_account_auto_access":False,"chat_export_supported":True,"mutations_executed":False},
      "manifest_path":str(mf),"manifest_sha256":_sha(mf.read_bytes()),"scanned_file_count":len(scanned),"chat_records_scanned":chat_count,
      "source_errors":errors,"category_counts":counts,"blockers":out,"next_actions":nexts,"scanned_files":scanned[:200]}
def inspect_workspace(manifest_dir,source_roots=None,chat_exports=None,max_files=5000,max_bytes_per_file=1048576):
    d=_p(manifest_dir)
    if not d.is_dir():raise ValueError("manifest_dir must be a directory")
    r=[inspect_project(str(x),source_roots,chat_exports,max_files,max_bytes_per_file) for x in sorted(d.glob("*.json"))]
    return {"skill":"project_recovery_inspector_v1","skill_version":VERSION,"project_count":len(r),"projects_with_blockers":sum(bool(x["blockers"]) for x in r),"reports":r}
def _md(r):
    a=[f"# Recovery report: {r['project_name']}","",f"- Project ID: `{r['project_id']}`",f"- Files scanned: {r['scanned_file_count']}",f"- Chat records scanned: {r['chat_records_scanned']}",f"- Blockers found: {len(r['blockers'])}","","## Next actions"]
    a += [f"- P{x['priority']} `{x['category']}`: {x['action']}" for x in r["next_actions"]] or ["- No blocker signatures found in supplied evidence."]
    a+=["","## Evidence"]
    for x in r["blockers"][:100]:
        loc=f"{x['source']}:{x['line']}" if x["line"] else x["source"];a.append(f"- **{x['category']}** [{x['severity']}] `{loc}`: {x['evidence']}")
    return "\n".join(a)+"\n"
def write_report(manifest_path,output_dir,source_roots=None,chat_exports=None,max_files=5000,max_bytes_per_file=1048576):
    r=inspect_project(manifest_path,source_roots,chat_exports,max_files,max_bytes_per_file);o=_p(output_dir);o.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r"[^A-Za-z0-9._-]+","_",r["project_id"]).strip("_") or "project";jp=o/f"{stem}.recovery.json";mp=o/f"{stem}.recovery.md"
    jp.write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");mp.write_text(_md(r),encoding="utf-8")
    return {"project_id":r["project_id"],"json_report":str(jp),"markdown_report":str(mp),"blocker_count":len(r["blockers"])}
def register_project_recovery_tools(registry):
    registry.register("recovery.inspect_project",inspect_project,risk="read",description="Deep-inspect real project files and optional user-authorized chat exports, classify blockers, and generate evidence-linked repair paths.")
    registry.register("recovery.inspect_workspace",inspect_workspace,risk="read",description="Inspect every project manifest in a directory without modifying state.")
    registry.register("recovery.write_report",write_report,risk="write",description="Write evidence-linked JSON and Markdown recovery reports after explicit approval.")
