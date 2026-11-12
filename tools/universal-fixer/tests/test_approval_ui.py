"""Live HTTP/loopback integration tests; no browser simulation success claim."""
import http.client
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from fixer.approval_ui import ApprovalServer,handler_factory,PAGE
from fixer.repair import make_plan,validate_plan


def git(path,*args):
    p=subprocess.run(['git',*args],cwd=path,capture_output=True,text=True)
    if p.returncode:raise AssertionError(p.stderr)
    return p.stdout.strip()

class LocalApprovalServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.repo=self.root/'source';self.repo.mkdir()
        git(self.repo,'init','-q','-b','main')
        git(self.repo,'config','user.name','Local Tester');git(self.repo,'config','user.email','dev@example.invalid')
        (self.repo/'core.py').write_text('def answer():\n    return 41\n')
        (self.repo/'test_core.py').write_text('import unittest\nfrom core import answer\nclass TestCore(unittest.TestCase):\n    def test_answer(self): self.assertEqual(answer(),42)\n')
        git(self.repo,'add','core.py','test_core.py');git(self.repo,'commit','-q','-m','baseline')
        self.plan=make_plan(self.repo,'local:issue:100','core.py','return 41','return 42',
                            [['python','-m','unittest','discover','-p','test_core.py','-v']], 'fix: answer matches contract')
        self.digest=validate_plan(self.plan)
        self.planfile=self.root/'plan.json';self.planfile.write_text(json.dumps(self.plan))
        self.evidence=self.root/'evidence.json'
        self.server=ApprovalServer(('127.0.0.1',0),handler_factory(),self.repo,self.planfile,self.evidence,timeout=15,token='test-secure-token-123')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.port=self.server.server_address[1]
    def tearDown(self):
        self.server.shutdown();self.thread.join(timeout=3);self.server.server_close();self.temp.cleanup()
    def request(self,method,path,body=None,token=None,origin=None):
        h={}
        if token:h['Authorization']='Bearer '+token
        if origin:h['Origin']=origin
        if body is not None:
            body=json.dumps(body);h['Content-Type']='application/json'
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=30)
        try:
            c.request(method,path,body=body,headers=h)
            r=c.getresponse();v=r.read().decode();return r.status,v
        finally:c.close()
    def test_no_key_leak_on_public_page(self):
        status,html=self.request('GET','/')
        self.assertEqual(status,200)
        self.assertNotIn('test-secure-token-123',html)
        self.assertIn('data-choice="A"',html)
    def test_plan_requires_strong_token(self):
        self.assertEqual(self.request('GET','/api/plan')[0],401)
        self.assertEqual(self.request('GET','/api/plan',token='wrong')[0],401)
        status,body=self.request('GET','/api/plan',token='test-secure-token-123')
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['plan_sha256'],self.digest)
    def test_mutation_requires_same_origin(self):
        status,_=self.request('POST','/api/decision',{'choice':'A','plan_sha256':self.digest},
                              token='test-secure-token-123',origin='http://attacker.invalid')
        self.assertEqual(status,403)
        self.assertFalse(self.evidence.exists())
    def test_stale_approval_is_rejected(self):
        status,body=self.request('POST','/api/decision',{'choice':'A','plan_sha256':'0'*64},
                               token='test-secure-token-123',origin=f'http://127.0.0.1:{self.port}')
        self.assertEqual(status,409)
        self.assertIn('Plan changed',body)
    def test_hold_logs_and_does_not_execute(self):
        status,body=self.request('POST','/api/decision',{'choice':'B','plan_sha256':self.digest},
                               token='test-secure-token-123',origin=f'http://127.0.0.1:{self.port}')
        self.assertEqual(status,200,body)
        self.assertEqual(json.loads(body)['status'],'HELD')
        self.assertFalse(self.evidence.exists())
        self.assertTrue(self.evidence.with_suffix('.owner-decisions.jsonl').exists())
    def test_button_a_executes_real_red_green_git_commit(self):
        status,body=self.request('POST','/api/decision',{'choice':'A','plan_sha256':self.digest},
                               token='test-secure-token-123',origin=f'http://127.0.0.1:{self.port}')
        self.assertEqual(status,200,body)
        result=json.loads(body)
        self.assertEqual(result['status'],'LOCAL_COMMIT_TESTED')
        self.assertTrue(self.evidence.exists())
        self.assertEqual(git(self.repo,'rev-parse',result['branch']),result['commit'])
        self.assertIn('return 41',(self.repo/'core.py').read_text())
        duplicate,_=self.request('POST','/api/decision',{'choice':'A','plan_sha256':self.digest},
                               token='test-secure-token-123',origin=f'http://127.0.0.1:{self.port}')
        self.assertEqual(duplicate,409)

if __name__=='__main__':unittest.main()