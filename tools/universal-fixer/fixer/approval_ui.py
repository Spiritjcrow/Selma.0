"""Loopback-only authenticated owner approval UI; no cloud, cookies or auto-run.

The random bearer token is created fresh each launch, never persisted or placed
in a URL. Enter it once in the local browser. Only an authenticated explicit
A action may call the RED->GREEN worktree executor.
"""
from __future__ import annotations
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit
from .core import utcnow
from .repair import load_plan, preflight, execute, RepairError

PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Selma Fixer — Owner Gate</title>
<style>body{font:16px system-ui;background:#0b1422;color:#edf4ff;max-width:760px;margin:0 auto;padding:18px}h1{font-size:1.5rem}section{background:#152438;border:1px solid #36485e;padding:16px;border-radius:12px;margin:14px 0}input,button{font:inherit;padding:12px;border-radius:9px}input{width:min(96%,540px);background:#091525;color:#fff;border:1px solid #7792b7}button{margin:5px;background:#233e59;color:#fff;border:1px solid #6784a6;cursor:pointer}button:disabled{opacity:.4;cursor:not-allowed}button.primary{background:#0b7467}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem}small{color:#bfd2e5}.error{color:#ff9999}</style>
</head><body><h1>Selma° Fixer — owner approval</h1><p>Local to this computer. Nothing is pushed, deployed or charged. Review the source-bound patch and test commands before approving.</p>
<section><label for="token">One-session owner token</label><p><input id="token" type="password" autocomplete="off" spellcheck="false" placeholder="Paste the token shown in your local terminal"></p><button id="load">Load current repair plan</button><small>Token stays in this page's memory; it is never saved in browser storage.</small></section>
<section id="review" hidden><strong id="task"></strong><pre id="details"></pre><button class="primary" data-choice="A">A — Approve and run tests/commit</button><button data-choice="B">B — Hold</button><button data-choice="C">C — Request more evidence</button><button data-choice="D">D — Reject</button></section>
<section><strong>Execution evidence</strong><pre id="status" role="status" aria-live="polite">No plan loaded.</pre></section>
<script>
(()=>{'use strict';let token='',digest='',busy=false;const $=id=>document.getElementById(id);let buttons=()=>document.querySelectorAll('[data-choice]');
async function call(route,options={}){const res=await fetch(route,{...options,headers:{Authorization:'Bearer '+token,...(options.body?{'Content-Type':'application/json'}:{})},cache:'no-store'});const raw=await res.text();let data;try{data=JSON.parse(raw)}catch{throw Error('Unexpected server response '+res.status)}if(!res.ok)throw Error(data.error||('HTTP '+res.status));return data}
async function load(){token=$('token').value.trim();$('status').textContent='Checking ownership token and current Git source…';try{const d=await call('/api/plan');digest=d.plan_sha256;$('task').textContent=d.task_id;$('details').textContent=JSON.stringify({source_commit:d.base_sha,file:d.file,expected_file_sha256:d.file_sha256,before:d.before,after:d.after,tests:d.tests,plan_sha256:d.plan_sha256},null,2);$('review').hidden=false;$('status').textContent='Ready for an explicit decision. Approval creates only an isolated local repair branch/commit.'}catch(e){$('review').hidden=true;$('status').textContent='BLOCKED: '+e.message}}
async function decide(choice){if(busy||!digest)return;busy=true;buttons().forEach(b=>b.disabled=true);$('status').textContent='Applying owner choice '+choice+'. A will run real tests and can take time…';try{const d=await call('/api/decision',{method:'POST',body:JSON.stringify({choice,plan_sha256:digest})});$('status').textContent=JSON.stringify(d,null,2)}catch(e){$('status').textContent='BLOCKED: '+e.message}finally{busy=false;buttons().forEach(b=>b.disabled=false)}}
$('load').addEventListener('click',load);buttons().forEach(b=>b.addEventListener('click',()=>decide(b.dataset.choice)));
})();
</script></body></html>'''

class ApprovalServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self, address, handler, repo, plan_path, evidence, timeout=120, token=None):
        if address[0]!='127.0.0.1':raise ValueError('Only 127.0.0.1 loopback binding allowed')
        self.repo=Path(repo).resolve();self.plan_path=Path(plan_path).resolve()
        self.evidence=Path(evidence).resolve();self.timeout=timeout
        self.owner_token=token or secrets.token_urlsafe(32)
        self.operation_lock=threading.Lock()
        super().__init__(address,handler)

def handler_factory():
    class Handler(BaseHTTPRequestHandler):
        server: ApprovalServer
        def log_message(self,fmt,*args):
            # Don't log Authorization, file paths, request bodies, or private plan content.
            pass
        def respond(self,code,payload,content_type='application/json; charset=utf-8'):
            data=payload.encode('utf8') if isinstance(payload,str) else json.dumps(payload,ensure_ascii=False).encode('utf8')
            self.send_response(code);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store, max-age=0')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)
        def authorize(self):
            host=self.headers.get('Host','')
            if host!=f'127.0.0.1:{self.server.server_address[1]}':
                self.respond(403,{'error':'Invalid request host'});return False
            value=self.headers.get('Authorization','')
            expected='Bearer '+self.server.owner_token
            if not hmac.compare_digest(value,expected):
                self.respond(401,{'error':'Private token required'});return False
            return True
        def do_GET(self):
            if urlsplit(self.path).path=='/' and self.headers.get('Host','')==f'127.0.0.1:{self.server.server_address[1]}':
                self.respond(200,PAGE,'text/html; charset=utf-8');return
            if urlsplit(self.path).path!='/api/plan':
                self.respond(404,{'error':'Not found'});return
            if not self.authorize():return
            try:
                p,d=load_plan(self.server.plan_path)
                _,head=preflight(self.server.repo,p)
                c=p['change']
                self.respond(200,{'task_id':p['task_id'],'base_sha':head,'plan_sha256':d,'file':c['path'],
                                  'file_sha256':c['file_sha256'],'before':c['before'],'after':c['after'],'tests':p['tests']})
            except (RepairError,OSError) as e:self.respond(409,{'error':str(e)})
        def do_POST(self):
            if urlsplit(self.path).path!='/api/decision':
                self.respond(404,{'error':'Not found'});return
            if not self.authorize():return
            origin=self.headers.get('Origin','')
            expected_origin=f'http://127.0.0.1:{self.server.server_address[1]}'
            if origin!=expected_origin:
                self.respond(403,{'error':'Browser origin not authorized'});return
            length=self.headers.get('Content-Length','')
            if not length.isdigit() or not 1<=int(length)<=512:
                self.respond(400,{'error':'Invalid request size'});return
            try:
                data=json.loads(self.rfile.read(int(length)))
                if not isinstance(data,dict) or set(data)!={'choice','plan_sha256'} or data['choice'] not in ('A','B','C','D'):
                    self.respond(400,{'error':'Unknown decision'});return
                if not self.server.operation_lock.acquire(blocking=False):
                    self.respond(409,{'error':'Another decision is running'});return
                try:
                    plan,digest=load_plan(self.server.plan_path)
                    preflight(self.server.repo,plan)
                    if not hmac.compare_digest(str(data['plan_sha256']),digest):
                        self.respond(409,{'error':'Plan changed; refresh review and authorize exact version'});return
                    choice=data['choice']
                    if choice=='A':
                        result=execute(self.server.repo,plan,digest,self.server.evidence,timeout=self.server.timeout)
                        self.respond(200 if result['status']=='LOCAL_COMMIT_TESTED' else 409,result)
                    else:
                        # Save a non-executing decision to a write-once sidecar; no external action.
                        path=self.server.evidence.with_suffix('.owner-decisions.jsonl')
                        path.parent.mkdir(parents=True,exist_ok=True)
                        fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
                        try:
                            with os.fdopen(fd,'a',encoding='utf8') as f:
                                f.write(json.dumps({'at':utcnow(),'choice':choice,'plan_sha256':digest},sort_keys=True)+'\n')
                        except Exception:raise
                        self.respond(200,{'status':{'B':'HELD','C':'EVIDENCE_REQUESTED','D':'REJECTED'}[choice],
                                          'plan_sha256':digest,'external_effects':'NONE'})
                finally:self.server.operation_lock.release()
            except (RepairError,OSError,ValueError,KeyError,TypeError) as e:
                self.respond(409,{'error':str(e)})
    return Handler

def serve(repo,plan_path,evidence,port=8768,timeout=120):
    if not 1<=port<=65535:raise ValueError('Invalid port')
    with ApprovalServer(('127.0.0.1',port),handler_factory(),repo,plan_path,evidence,timeout) as server:
        print(f'Open http://127.0.0.1:{server.server_address[1]}/ in this computer browser')
        print('One-session private token (do not share or log): '+server.owner_token)
        print('Server binds to loopback only. CTRL+C stops taking new requests. No remote users can connect directly.')
        try:server.serve_forever(poll_interval=.25)
        except KeyboardInterrupt:pass