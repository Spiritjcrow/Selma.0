import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

RUNNER = Path(__file__).resolve().parents[1] / 'verify_duo_handoff_offline.py'
spec = importlib.util.spec_from_file_location('duo_runner', RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def cmd(root, *args):
    p = subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True)
    return p.stdout.strip()


class HarnessProvenanceFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        cmd(self.root, 'init', '-q')
        cmd(self.root, 'config', 'user.email', 'test@example.invalid')
        cmd(self.root, 'config', 'user.name', 'Synthetic QA')
        for file in runner.SOURCE_FILES + runner.TEST_FILES:
            p = self.root / file
            p.parent.mkdir(parents=True, exist_ok=True)
            if file in runner.TEST_FILES:
                p.write_text('import unittest\nclass TestSynthetic(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n', encoding='utf8')
            else:
                p.write_text('def local_only():\n    return True\n', encoding='utf8')
        (self.root / '.gitignore').write_text('tests/test_duo_ignored.py\n', encoding='utf8')
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic exact source')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')

    def tearDown(self):
        self.temp.cleanup()

    def verify(self, expected=None):
        return runner.verify(self.root, expected or self.sha, 20)

    def test_clean_exact_sha_runs_only_four_tests(self):
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 0, report)
        self.assertEqual(report['tests'], 'PASS')
        self.assertEqual(report['test_methods_reported'], 4)
        self.assertEqual(report['state'], 'REVIEW')

    def test_wrong_sha_blocks_without_execution(self):
        report, exit_code = self.verify('0' * 40)
        self.assertEqual(exit_code, 2)
        self.assertEqual(report['tests'], 'NOT_RUN')

    def test_untracked_matching_test_blocks_without_execution(self):
        (self.root / 'tests/test_duo_injected.py').write_text('raise RuntimeError("must not execute")\n')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2)
        self.assertEqual(report['tests'], 'NOT_RUN')

    def test_ignored_matching_test_blocks_without_execution(self):
        (self.root / 'tests/test_duo_ignored.py').write_text('raise RuntimeError("must not execute")\n')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2)
        self.assertIn('pinned allowlist', report['blocker'])
        self.assertEqual(report['tests'], 'NOT_RUN')

    def test_untracked_non_test_file_blocks(self):
        (self.root / 'extra.txt').write_text('harmless')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2)
        self.assertEqual(report['tests'], 'NOT_RUN')

    def test_modified_tracked_source_blocks(self):
        (self.root / runner.SOURCE_FILES[0]).write_text('def changed():\n    pass\n')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2)
        self.assertEqual(report['tests'], 'NOT_RUN')

    def test_assume_unchanged_tracked_test_blocks(self):
        path = runner.TEST_FILES[0]
        cmd(self.root, 'update-index', '--assume-unchanged', path)
        (self.root / path).write_text('raise RuntimeError("must not execute")\n')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN')
        self.assertIn('on-disk Git blob differs', report['blocker'])

    def test_skip_worktree_tracked_test_blocks(self):
        path = runner.TEST_FILES[0]
        cmd(self.root, 'update-index', '--skip-worktree', path)
        (self.root / path).write_text('raise RuntimeError("must not execute")\n')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN')
        self.assertIn('on-disk Git blob differs', report['blocker'])

    def test_missing_allowlisted_file_blocks(self):
        (self.root / runner.TEST_FILES[0]).unlink()
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2)
        self.assertEqual(report['tests'], 'NOT_RUN')

    def test_ignored_extra_test_symlink_blocks(self):
        target = self.root / runner.TEST_FILES[0]
        try:
            (self.root / 'tests/test_duo_ignored.py').symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks not available in this test environment')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2)
        self.assertEqual(report['tests'], 'NOT_RUN')

if __name__ == '__main__':
    unittest.main()
