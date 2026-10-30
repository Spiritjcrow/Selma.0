"""Offline tests for fixed, network-disabled Docker test gate (no Docker daemon)."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools import selma_candidate_forge as forge
from tools import selma_candidate_review as review
from tools import selma_candidate_sandbox as sandbox

IMAGE = 'python@sha256:'+'a'*64


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init','-q')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','user.name','Fixture')
        path = self.root / 'core/example.py'
        path.parent.mkdir()
        path.write_text('VALUE=1\n')
        test = self.root/'tests/test_example.py'
        test.parent.mkdir()
        test.write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
        self.git('add','.')
        self.git('commit','-qm','baseline')
        base=self.git('rev-parse','HEAD')
        self.prefix=forge.forge(self.root, {'base_sha':base,'target':'core/example.py',
                         'goal':'Improve the constant value.', 'model':'fixture'},
                         lambda *args: json.dumps({'target':'core/example.py','replacement':'VALUE=2\n'}))
        review.review(self.root,self.prefix.name)

    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.root,capture_output=True,
                              text=True,check=True).stdout.strip()

    def test_fixed_docker_controls(self):
        with tempfile.TemporaryDirectory() as src:
            cmd=sandbox.build_command(IMAGE,Path(src),'selma-test-fixed')
            self.assertIn('none',cmd)
            self.assertIn('--read-only',cmd)
            self.assertIn('--cap-drop',cmd)
            self.assertIn('ALL',cmd)
            self.assertIn('no-new-privileges',cmd)
            self.assertIn('never',cmd)
            self.assertIn('--pids-limit',cmd)
            self.assertIn('--memory',cmd)
            self.assertIn('readonly',cmd[cmd.index('--mount')+1])
            self.assertNotIn('--privileged',cmd)
            self.assertEqual('unittest',cmd[cmd.index('-m')+1])

    def test_unpinned_image_rejected(self):
        with tempfile.TemporaryDirectory() as src:
            for name in ('python:3.13', 'alpine:latest', 'evil@sha256:'+'a'*64):
                with self.subTest(name=name),self.assertRaises(forge.ForgeError):
                    sandbox.build_command(name,Path(src),'name')

    def test_evidence_valid(self):
        head,target,patch,digest=sandbox.read_evidence(self.root,self.prefix.name)
        self.assertEqual('core/example.py',target)
        self.assertEqual(self.git('rev-parse','HEAD'),head)
        self.assertTrue(patch)
        self.assertEqual(64,len(digest))

    def test_snapshot_applies_and_source_untouched(self):
        head,target,patch,digest=sandbox.read_evidence(self.root,self.prefix.name)
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'source'
            sandbox.snapshot_candidate(self.root,target,patch,digest,output)
            self.assertEqual('VALUE=2\n',(output/target).read_text())
        self.assertEqual('VALUE=1\n',(self.root/target).read_text())

    def test_modified_review_report_rejected(self):
        p=self.prefix.with_suffix('.review.json')
        report=json.loads(p.read_text())
        report['tests_executed']=True
        p.write_text(json.dumps(report))
        with self.assertRaisesRegex(forge.ForgeError, 'static review'):
            sandbox.read_evidence(self.root,self.prefix.name)

    def test_bad_patch_digest_rejected(self):
        p=self.prefix.with_suffix('.diff')
        p.write_text(p.read_text()+'\nhello')
        with self.assertRaisesRegex(forge.ForgeError, 'integrity mismatch'):
            sandbox.read_evidence(self.root,self.prefix.name)

    def test_kill_switch_rejected(self):
        forge.git_private(self.root,'SELMA_BUILD_STOP').touch()
        with self.assertRaisesRegex(forge.ForgeError, 'kill switch'):
            sandbox.run(self.root,self.prefix.name,IMAGE)

    def test_docker_not_installed_fails_closed(self):
        with patch.object(sandbox.shutil,'which',return_value=None):
            with self.assertRaisesRegex(forge.ForgeError, 'Docker'):
                sandbox.run(self.root,self.prefix.name,IMAGE)

    def test_cli_cleanup_timeout_reaps_process_and_fails_closed(self):
        import sys
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            original_popen = subprocess.Popen
            started = []

            def record_process(*args, **kwargs):
                proc = original_popen(*args, **kwargs)
                started.append(proc)
                return proc

            with patch.object(sandbox.subprocess, 'Popen', side_effect=record_process), \
                 patch.object(sandbox.subprocess, 'run',
                              side_effect=subprocess.TimeoutExpired(['docker', 'rm'], 15)):
                with self.assertRaisesRegex(forge.ForgeError, 'cleanup unverified'):
                    sandbox.run_bounded(
                        [sys.executable, '-c', 'import time; time.sleep(30)'],
                        stop, 'selma-test-timeout', time.monotonic() + 5)
            self.assertEqual(1, len(started))
            self.assertIsNotNone(started[0].poll())

    def test_cli_stop_reaps_process(self):
        import sys
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            original_popen = subprocess.Popen
            started = []

            def record_process(*args, **kwargs):
                proc = original_popen(*args, **kwargs)
                started.append(proc)
                return proc

            with patch.object(sandbox.subprocess, 'Popen', side_effect=record_process), \
                 patch.object(sandbox.subprocess, 'run',
                              return_value=subprocess.CompletedProcess([], 0, stdout='')):
                code = sandbox.run_bounded(
                    [sys.executable, '-c', 'import time; time.sleep(30)'],
                    stop, 'selma-test-stop', time.monotonic() + 5)
            self.assertEqual(130, code)
            self.assertEqual(1, len(started))
            self.assertIsNotNone(started[0].poll())

    def test_cli_already_removed_verified_absent(self):
        # docker run --rm can remove the container before docker rm -f runs.
        import sys
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            original_popen = subprocess.Popen
            started = []

            def record_process(*args, **kwargs):
                proc = original_popen(*args, **kwargs)
                started.append(proc)
                return proc

            with patch.object(sandbox.subprocess, 'Popen', side_effect=record_process), \
                 patch.object(sandbox.subprocess, 'run', side_effect=[
                     subprocess.CompletedProcess([], 1),
                     subprocess.CompletedProcess([], 0, stdout='')]) as cleanup:
                code = sandbox.run_bounded(
                    [sys.executable, '-c', 'import time; time.sleep(30)'],
                    stop, 'selma-test-absent', time.monotonic() + 5)
            self.assertEqual(130, code)
            self.assertEqual(2, cleanup.call_count)
            self.assertIsNotNone(started[0].poll())

    def test_cli_still_present_fails_closed_and_reaps(self):
        import sys
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            original_popen = subprocess.Popen
            started = []

            def record_process(*args, **kwargs):
                proc = original_popen(*args, **kwargs)
                started.append(proc)
                return proc

            with patch.object(sandbox.subprocess, 'Popen', side_effect=record_process), \
                 patch.object(sandbox.subprocess, 'run', side_effect=[
                     subprocess.CompletedProcess([], 0),
                     subprocess.CompletedProcess([], 0, stdout='selma-test-present\\n')]):
                with self.assertRaisesRegex(forge.ForgeError, 'cleanup unverified'):
                    sandbox.run_bounded(
                        [sys.executable, '-c', 'import time; time.sleep(30)'],
                        stop, 'selma-test-present', time.monotonic() + 5)
            self.assertIsNotNone(started[0].poll())

    def test_cli_inspection_failure_fails_closed_and_reaps(self):
        import sys
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            original_popen = subprocess.Popen
            started = []

            def record_process(*args, **kwargs):
                proc = original_popen(*args, **kwargs)
                started.append(proc)
                return proc

            with patch.object(sandbox.subprocess, 'Popen', side_effect=record_process), \
                 patch.object(sandbox.subprocess, 'run', side_effect=[
                     subprocess.CompletedProcess([], 1),
                     subprocess.CompletedProcess([], 1, stdout='')]):
                with self.assertRaisesRegex(forge.ForgeError, 'cleanup unverified'):
                    sandbox.run_bounded(
                        [sys.executable, '-c', 'import time; time.sleep(30)'],
                        stop, 'selma-test-inspect', time.monotonic() + 5)
            self.assertIsNotNone(started[0].poll())

    def test_invalid_timeout_rejected(self):
        with self.assertRaisesRegex(forge.ForgeError,'timeout'):
            sandbox.run(self.root,self.prefix.name,IMAGE,timeout_seconds=10)


if __name__=='__main__':
    unittest.main()
