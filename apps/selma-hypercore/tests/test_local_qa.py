"""Validate quality gate stops on errors, does not claim hosted verification."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_local_qa import execute, commands

class LocalQATests(unittest.TestCase):
    def test_python_only_plan(self):
        plan=commands(python_only=True)
        self.assertEqual(len(plan),1)
        self.assertEqual(plan[0][0],'python_unit')

    def test_no_empty_plan(self):
        with self.assertRaises(ValueError): execute([])

    def test_fail_closed_stops(self):
        plan=[('fail',[sys.executable,'-c','import sys;sys.exit(17)']),('should-not-run',[sys.executable,'-c','print(5)'])]
        report=execute(plan)
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(len(report['checks']),1)
        self.assertEqual(report['checks'][0]['exit_code'],17)
        self.assertFalse(report['hosted_ci_verified'])

    def test_pass_does_not_claim_android(self):
        plan=[('pass',[sys.executable,'-c','print("pass")'])]
        report=execute(plan)
        self.assertEqual(report['status'],'PASS')
        self.assertFalse(report['android_apk_tested'])

if __name__=='__main__': unittest.main()
