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

    def test_stop_racing_with_completed_cli_is_not_pass(self):
        # Even a completed zero-exit CLI cannot override an owner stop request.
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            with patch.object(sandbox.subprocess, 'Popen') as popen, \
                 patch.object(sandbox.subprocess, 'run',
                              return_value=subprocess.CompletedProcess([], 0, stdout='')):
                proc = popen.return_value
                proc.poll.return_value = 0
                proc.returncode = 0
                code = sandbox.run_bounded(['docker', 'run'], stop,
                                           'selma-stop-race', time.monotonic() + 5)
            self.assertEqual(130, code)

    def test_stop_after_bounded_run_prevents_pass_evidence(self):
        # A late stop must not be written as ISOLATED_TEST_PASS_REVIEW_REQUIRED.
        head, target, diff, digest = sandbox.read_evidence(self.root, self.prefix.name)
        stop = forge.git_private(self.root, 'SELMA_BUILD_STOP')

        def fake_snapshot(_root, _target, _patch, _digest, output):
            output.mkdir()

        def stop_then_return_zero(*_args):
            stop.touch()
            return 0

        from types import SimpleNamespace
        fake_docker = SimpleNamespace(run=lambda *_a, **_kw:
                                      subprocess.CompletedProcess([], 0))
        with patch.object(sandbox, 'read_evidence',
                          return_value=(head, target, diff, digest)), \
             patch.object(sandbox.forge, 'clean_head', return_value=head), \
             patch.object(sandbox.shutil, 'which', return_value='/usr/bin/docker'), \
             patch.object(sandbox, 'subprocess', fake_docker), \
             patch.object(sandbox, 'snapshot_candidate', side_effect=fake_snapshot), \
             patch.object(sandbox, 'run_bounded', side_effect=stop_then_return_zero):
            with self.assertRaisesRegex(forge.ForgeError, 'kill switch'):
                sandbox.run(self.root, self.prefix.name, IMAGE)
        self.assertFalse(self.prefix.with_suffix('.sandbox.json').exists())

    def test_cli_terminate_exit_race_reaps_and_honors_stop(self):
        # The CLI may exit between poll() and terminate(); do not lose stop intent.
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            with patch.object(sandbox.subprocess, 'Popen') as popen, \
                 patch.object(sandbox.subprocess, 'run', side_effect=[
                     subprocess.CompletedProcess([], 0),
                     subprocess.CompletedProcess([], 0, stdout='')]):
                proc = popen.return_value
                proc.poll.return_value = None
                proc.terminate.side_effect = ProcessLookupError()
                proc.wait.return_value = 0
                code = sandbox.run_bounded(['docker', 'run'], stop,
                                           'selma-terminate-race', time.monotonic() + 5)
            self.assertEqual(130, code)
            proc.wait.assert_called_once_with(timeout=3)

    def test_cli_kill_exit_race_reaps_and_honors_stop(self):
        # The CLI may exit after wait() times out but before kill().
        import time
        with tempfile.TemporaryDirectory() as d:
            stop = Path(d) / 'STOP'
            stop.touch()
            with patch.object(sandbox.subprocess, 'Popen') as popen, \
                 patch.object(sandbox.subprocess, 'run', side_effect=[
                     subprocess.CompletedProcess([], 0),
                     subprocess.CompletedProcess([], 0, stdout='')]):
                proc = popen.return_value
                proc.poll.return_value = None
                proc.wait.side_effect = [subprocess.TimeoutExpired(['docker', 'run'], 3), 0]
                proc.kill.side_effect = ProcessLookupError()
                code = sandbox.run_bounded(['docker', 'run'], stop,
                                           'selma-kill-race', time.monotonic() + 5)
            self.assertEqual(130, code)
            self.assertEqual(2, proc.wait.call_count)

    def test_invalid_timeout_rejected(self):
        with self.assertRaisesRegex(forge.ForgeError,'timeout'):
            sandbox.run(self.root,self.prefix.name,IMAGE,timeout_seconds=10)


if __name__=='__main__':
    unittest.main()
