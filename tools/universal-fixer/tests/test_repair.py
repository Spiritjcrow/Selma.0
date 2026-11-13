"""End-to-end local source repair tests: REAL git, REAL pytest/unittest, REAL commit."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from fixer.repair import RepairError, make_plan, validate_plan, execute, load_plan, safe_test, clean_relative


def run(cwd,*cmd):
    p=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True)
    if p.returncode:raise AssertionError(p.stderr+' '+p.stdout)
    return p.stdout.strip()

class RepairIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        run(self.repo,'git','init','-q','-b','main')
        run(self.repo,'git','config','user.email','test@example.invalid')
        run(self.repo,'git','config','user.name','Fixture Developer')
        (self.repo/'mathops.py').write_text('def add(a,b):\n    return a - b\n')
        (self.repo/'test_mathops.py').write_text('import unittest\nfrom mathops import add\nclass TestAdd(unittest.TestCase):\n    def test_add(self): self.assertEqual(add(2,3),5)\n')
        run(self.repo,'git','add','mathops.py','test_mathops.py');run(self.repo,'git','commit','-q','-m','fixture baseline')
        self.plan=make_plan(self.repo,'fixture:issue:1','mathops.py','return a - b','return a + b',
                            [['python','-m','unittest','discover','-p','test_mathops.py','-v']],
                            'fix: correct addition in mathops')
        self.digest=validate_plan(self.plan)
    def tearDown(self):self.temp.cleanup()
    def test_red_green_commit_with_sha_evidence(self):
        out=self.root/'result.json'
        result=execute(self.repo,self.plan,self.digest,out)
        self.assertEqual(result['status'],'LOCAL_COMMIT_TESTED',result)
        self.assertNotEqual(result['source_head'],result['commit'])
        self.assertNotEqual(result['baseline'][0]['exit_code'],0)
        self.assertEqual(result['after'][0]['exit_code'],0)
        self.assertEqual(result['external_validation'],'NOT_RUN')
        branch_commit=run(self.repo,'git','rev-parse',result['branch'])
        self.assertEqual(branch_commit,result['commit'])
        self.assertIn('return a - b',(self.repo/'mathops.py').read_text())  # main unchanged
        self.assertTrue(json.loads(out.read_text())['commit'])
    def test_approval_digest_wrong_fails_no_branch(self):
        with self.assertRaises(RepairError):execute(self.repo,self.plan,'0'*64,self.root/'err.json')
        self.assertEqual(run(self.repo,'git','branch','--list','fixer/*'),'')
    def test_baseline_green_disallows_unjustified_fix(self):
        (self.repo/'test_mathops.py').write_text('import unittest\nfrom mathops import add\nclass TestMath(unittest.TestCase):\n    def test_expected_difference(self): self.assertEqual(add(5,3),2)\n')
        run(self.repo,'git','add','test_mathops.py');run(self.repo,'git','commit','-q','-m','fixture baseline green')
        plan=make_plan(self.repo,'fixture:issue:2','mathops.py','return a - b','return a + b',
                            [['python','-m','unittest','discover','-p','test_mathops.py','-v']], 'fix: correction only if failure')
        result=execute(self.repo,plan,validate_plan(plan),self.root/'green.json')
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('already passes',result['error'])
        self.assertIsNone(result['commit'])
    def test_post_patch_test_fails_no_commit(self):
        plan=make_plan(self.repo,'fixture:issue:3','mathops.py','return a - b','return a * b',
                            [['python','-m','unittest','discover','-p','test_mathops.py','-v']], 'fix: intentionally invalid variant')
        res=execute(self.repo,plan,validate_plan(plan),self.root/'fail.json')
        self.assertEqual(res['status'],'BLOCKED')
        self.assertIsNone(res['commit'])
        self.assertIn('Post-fix',res['error'])
    def test_changed_head_refuses_stale_plan(self):
        (self.repo/'notes.md').write_text('updated')
        run(self.repo,'git','add','notes.md');run(self.repo,'git','commit','-q','-m','update base')
        with self.assertRaises(RepairError):execute(self.repo,self.plan,self.digest,self.root/'stale.json')
    def test_dirty_checkout_refuses(self):
        (self.repo/'untracked').write_text('do not ignore')
        with self.assertRaises(RepairError):execute(self.repo,self.plan,self.digest,self.root/'dirty.json')
    def test_path_traversal_and_symlink_refused(self):
        for name in ('../outside.py','/tmp/x.py','a/../../secret.py','.git/config','a\\b.py'):
            with self.assertRaises(RepairError):clean_relative(name)
        (self.repo/'link.py').symlink_to(self.repo/'mathops.py')
        with self.assertRaises(RepairError):make_plan(self.repo,'fixture:issue:4','link.py','a','b',[['python','-m','unittest']], 'fix: invalid symlink')
    def test_test_command_injection_refused(self):
        self.assertFalse(safe_test(['sh','-c','rm -rf /']))
        self.assertFalse(safe_test(['python','-c','print(1)']))
        self.assertFalse(safe_test(['git','push','--force']))
        bad=dict(self.plan,tests=[['bash','-lc','echo unsafe']])
        with self.assertRaises(RepairError):validate_plan(bad)
    def test_invalid_head_input_fails(self):
        bad=dict(self.plan,base_sha='main')
        with self.assertRaises(RepairError):validate_plan(bad)
    def test_no_double_overwrite_output_or_branch(self):
        out=self.root/'done.json'
        r=execute(self.repo,self.plan,self.digest,out)
        self.assertEqual(r['status'],'LOCAL_COMMIT_TESTED')
        with self.assertRaises(RepairError):execute(self.repo,self.plan,self.digest,out)
        with self.assertRaises(RepairError):execute(self.repo,self.plan,self.digest,self.root/'new.json')

if __name__=='__main__':unittest.main()