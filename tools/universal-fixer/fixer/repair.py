"""Fail-closed, RED->GREEN local Git repair executor.

This is a *real* bounded source repair worker. It neither invents patches nor
claims physical/cloud acceptance. All effects stay on a new local Git branch.
The owner must approve the exact SHA-256 plan from a trusted local interface.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from .core import stable_json, utcnow

class RepairError(RuntimeError): pass

SAFE_GIT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,100}$")
SAFE_TASK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,180}$")

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def invoke(argv, cwd, timeout=30, env=None):
    if not argv or any(not isinstance(a, str) or '\0' in a for a in argv):
        raise RepairError('Invalid subprocess argv')
    e=os.environ.copy()
    e.update({'GIT_TERMINAL_PROMPT':'0','CI':'true','PYTHONDONTWRITEBYTECODE':'1'})
    if env:e.update(env)
    try:
        result=subprocess.run(argv,cwd=str(cwd),capture_output=True,text=True,
                              errors='replace',timeout=timeout,env=e,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise RepairError(f'Command timed out after {timeout}s: {argv[0]}') from None
    except OSError as ex:
        raise RepairError(f'Command unavailable: {argv[0]} ({type(ex).__name__})') from None
    return result

def git(repo,*args,timeout=30,ok=True):
    r=invoke(['git',*args],repo,timeout)
    if ok and r.returncode:
        raise RepairError('Git operation failed: '+(r.stderr or r.stdout).strip()[:1200])
    return r

def clean_relative(path):
    if not isinstance(path,str) or not path or '\\' in path or '\0' in path:
        raise RepairError('Unsafe relative file path')
    p=Path(path)
    if p.is_absolute() or any(x in ('.','..','') for x in path.split('/')) or '.git' in p.parts:
        raise RepairError('Unsafe or Git-internal file path')
    if p.suffix not in ('.py','.js','.ts','.json','.md','.yml','.yaml','.kt','.java','.xml','.gradle','.txt'):
        raise RepairError('File type is not in the source-review allowlist')
    return p

def checked_target(worktree,rel):
    target=worktree/clean_relative(rel)
    if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(worktree.resolve()):
        raise RepairError('Source target is absent, symlinked, or outside worktree')
    if target.stat().st_size>2_000_000:raise RepairError('Oversize file; use manual review')
    return target

def safe_test(argv):
    """No shell, arbitrary executable, or chaining. Tests still run repo code."""
    if not isinstance(argv,list) or len(argv)<2 or len(argv)>24 or any(not isinstance(x,str) or not x or '\0' in x or len(x)>260 for x in argv):
        return False
    if argv[0] in ('python', 'python3', sys.executable):
        return len(argv)>=3 and argv[1]=='-m' and argv[2] in ('unittest','pytest','compileall') and not any(x.startswith('-c') for x in argv[3:])
    if argv[0]=='pytest':return True
    if argv[0]=='node':return len(argv)>=3 and argv[1]=='--check'
    if argv[0] in ('./gradlew','gradlew.bat'):
        return all(x in ('test','assembleDebug','lint','check','--offline','--no-daemon') for x in argv[1:])
    return False

def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)!={'task_id','base_sha','change','tests','commit_message'}:
        raise RepairError('Plan requires exactly task_id, base_sha, change, tests, commit_message')
    if not isinstance(plan['task_id'],str) or not SAFE_TASK.fullmatch(plan['task_id']):raise RepairError('Invalid task ID')
    if not re.fullmatch('[0-9a-f]{40}',str(plan['base_sha'])):raise RepairError('Expected full Git base SHA')
    change=plan['change']
    if not isinstance(change,dict) or set(change)!={'path','before','after','file_sha256'}:raise RepairError('Invalid patch schema')
    clean_relative(change['path'])
    for k in ('before','after'):
        if not isinstance(change[k],str) or not change[k] or len(change[k])>20000:raise RepairError('Patch text invalid or too large')
    if change['before']==change['after']:raise RepairError('No-op patch denied')
    if not re.fullmatch('[0-9a-f]{64}',str(change['file_sha256'])):raise RepairError('Expected file SHA-256')
    tests=plan['tests']
    if not isinstance(tests,list) or not 1<=len(tests)<=8 or not all(safe_test(t) for t in tests):raise RepairError('Tests must be allowlisted argv arrays')
    msg=plan['commit_message']
    if not isinstance(msg,str) or not 5<=len(msg)<=140 or '\n' in msg or '\r' in msg:raise RepairError('Invalid commit message')
    return sha256(stable_json(plan).encode('utf8'))

def load_plan(path):
    data=Path(path).read_bytes()
    if len(data)>100_000:raise RepairError('Plan file too large')
    try:plan=json.loads(data)
    except (ValueError,UnicodeError) as e:raise RepairError('Plan JSON invalid') from e
    return plan,validate_plan(plan)

def preflight(repo,plan):
    root=Path(repo).resolve()
    if not root.is_dir():raise RepairError('Local checkout not found')
    top=git(root,'rev-parse','--show-toplevel').stdout.strip()
    if Path(top).resolve()!=root:raise RepairError('Use the Git repository root, not a subfolder')
    current=git(root,'rev-parse','HEAD').stdout.strip()
    if current!=plan['base_sha']:raise RepairError('Base SHA changed: re-plan and approve again')
    if git(root,'status','--porcelain').stdout.strip():raise RepairError('Checkout has uncommitted/untracked files; preserve and review them first')
    target=checked_target(root,plan['change']['path'])
    data=target.read_bytes()
    if sha256(data)!=plan['change']['file_sha256']:raise RepairError('Patch target bytes changed: re-plan')
    try:txt=data.decode('utf8')
    except UnicodeError as e:raise RepairError('Target is not UTF-8 text') from e
    if txt.count(plan['change']['before'])!=1:raise RepairError('Patch search must match exactly once')
    return root,current

def make_plan(repo, task_id, path, before, after, tests, message):
    root=Path(repo).resolve()
    head=git(root,'rev-parse','HEAD').stdout.strip()
    target=checked_target(root,path)
    patch={'task_id':task_id,'base_sha':head,'change':{'path':path,'before':before,'after':after,'file_sha256':sha256(target.read_bytes())},'tests':tests,'commit_message':message}
    validate_plan(patch)
    preflight(root,patch)
    return patch

def run_checks(tests,worktree,timeout=120):
    results=[]
    for argv in tests:
        if not safe_test(argv):raise RepairError('Unapproved test command')
        r=invoke(argv,worktree,timeout)
        results.append({'argv':argv,'exit_code':r.returncode,'stdout_tail':r.stdout[-2400:], 'stderr_tail':r.stderr[-2400:]})
        if r.returncode!=0:break
    return results

def execute(repo,plan,approved_digest,output,timeout=120):
    """Create isolated branch; require RED baseline and GREEN corrected tests; commit.

    Failure is preserved in a local evidence JSON, and the temporary worktree is
    removed after the operation. No push, merge, bill, or deployment occurs.
    """
    digest=validate_plan(plan)
    if approved_digest!=digest:raise RepairError('Exact plan digest approval is missing or stale')
    root,head=preflight(repo,plan)
    evidence_path=Path(output).resolve()
    if evidence_path.exists():raise RepairError('Output already exists; no overwrite')
    evidence_path.parent.mkdir(parents=True,exist_ok=True)
    task=re.sub('[^A-Za-z0-9-]','-',plan['task_id'])[:42]
    branch='fixer/'+task+'-'+digest[:12]
    if not SAFE_GIT_REF.fullmatch(branch):raise RepairError('Invalid generated branch')
    if git(root,'show-ref','--verify','--quiet','refs/heads/'+branch,ok=False).returncode==0:
        raise RepairError('Branch already exists; do not overwrite or run twice')
    evidence={'plan_sha256':digest,'task_id':plan['task_id'],'started_at':utcnow(),'source_head':head,'branch':branch,
              'status':'BLOCKED','baseline':None,'after':None,'commit':None,'external_validation':'NOT_RUN'}
    with tempfile.TemporaryDirectory(prefix='selma-fixer-') as td:
        worktree=Path(td)/'checkout'
        added=False
        try:
            git(root,'worktree','add','--detach',str(worktree),head,timeout=40)
            added=True
            baseline=run_checks(plan['tests'],worktree,timeout)
            evidence['baseline']=baseline
            if baseline and all(x['exit_code']==0 for x in baseline):
                raise RepairError('Baseline already passes; cannot claim this patch repairs a reproduced failure')
            if not baseline or baseline[-1]['exit_code']==0:
                raise RepairError('No failing test observed')
            target=checked_target(worktree,plan['change']['path'])
            source=target.read_text(encoding='utf8')
            before=plan['change']['before'];after=plan['change']['after']
            if source.count(before)!=1:raise RepairError('Patch target mismatch in worktree')
            target.write_text(source.replace(before,after,1),encoding='utf8',newline='')
            tested=run_checks(plan['tests'],worktree,timeout)
            evidence['after']=tested
            if len(tested)!=len(plan['tests']) or any(x['exit_code']!=0 for x in tested):
                raise RepairError('Post-fix test failed; no commit created')
            changed=git(worktree,'diff','--name-only').stdout.strip().splitlines()
            if changed!=[plan['change']['path']]:raise RepairError('Unexpected source changes; abort')
            git(worktree,'switch','-c',branch)
            git(worktree,'add','--',plan['change']['path'])
            staged=git(worktree,'diff','--cached','--name-only').stdout.strip().splitlines()
            if staged!=[plan['change']['path']]:raise RepairError('Unexpected staged files; abort')
            # Author is explicitly marked as the local automated worker; no impersonation.
            git(worktree,'-c','user.name=Selma Fixer Bot','-c','user.email=selma-fixer@users.noreply.github.com',
                'commit','-m',plan['commit_message'],timeout=40)
            commit=git(worktree,'rev-parse','HEAD').stdout.strip()
            if not re.fullmatch('[0-9a-f]{40}',commit):raise RepairError('Git commit not verified')
            evidence['commit']=commit;evidence['status']='LOCAL_COMMIT_TESTED'
            # Existing branch is retained when worktree is removed.
        except RepairError as ex:
            evidence['error']=str(ex)
        finally:
            evidence['finished_at']=utcnow()
            if added:
                git(root,'worktree','remove','--force',str(worktree),timeout=40,ok=False)
            evidence_path.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return evidence