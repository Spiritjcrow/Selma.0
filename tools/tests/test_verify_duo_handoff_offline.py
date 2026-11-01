import importlib.util
import os
import py_compile
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

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

    def test_inherited_pythonpath_cannot_replace_unittest_runner(self):
        # A caller-controlled PYTHONPATH must not replace the stdlib unittest
        # module with a fake executable that prints a fabricated PASS summary.
        with tempfile.TemporaryDirectory() as external:
            fake = Path(external) / 'unittest.py'
            fake.write_text(
                'import sys\n'
                'sys.stderr.write("Ran 999 tests in 0.001s\\n\\nOK\\n")\n',
                encoding='utf8',
            )
            with mock.patch.dict(os.environ, {'PYTHONPATH': external}):
                report, exit_code = self.verify()
        self.assertEqual(exit_code, 0, report)
        self.assertEqual(report['tests'], 'PASS')
        self.assertEqual(report['test_methods_reported'], 4, report)

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

    def test_assume_unchanged_package_initializer_blocks(self):
        # tests/__init__.py can run through imports from the pinned test set.
        path = 'tests/__init__.py'
        cmd(self.root, 'update-index', '--assume-unchanged', path)
        (self.root / path).write_text('raise RuntimeError("UNPINNED_PACKAGE_INIT")\n')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN')
        self.assertIn('on-disk Git blob differs', report['blocker'])

    def test_skip_worktree_transitive_core_dependency_blocks(self):
        # core/__init__.py imports core.protocols before core.duo_handoff.
        path = 'core/protocols.py'
        cmd(self.root, 'update-index', '--skip-worktree', path)
        (self.root / path).write_text('raise RuntimeError("UNPINNED_CORE_DEPENDENCY")\n')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN')
        self.assertIn('on-disk Git blob differs', report['blocker'])

    def test_ignored_timestamp_valid_bytecode_cannot_replace_pinned_test(self):
        path = self.root / runner.TEST_FILES[0]
        original = path.read_text(encoding='utf8')
        original_stat = path.stat()
        poison = 'raise RuntimeError("POISONED_BYTECODE_EXECUTED")\n'
        self.assertLessEqual(len(poison), len(original))
        poison += ' ' * (len(original) - len(poison))
        path.write_text(poison, encoding='utf8')
        cached = Path(importlib.util.cache_from_source(str(path)))
        cached.parent.mkdir(parents=True, exist_ok=True)
        py_compile.compile(str(path), cfile=str(cached), doraise=True)
        path.write_text(original, encoding='utf8')
        os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        (self.root / '.git/info/exclude').write_text('__pycache__/\n', encoding='utf8')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        self.assertEqual(cmd(self.root, 'hash-object', runner.TEST_FILES[0]),
                         cmd(self.root, 'rev-parse', 'HEAD:' + runner.TEST_FILES[0]))
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 0, report)
        self.assertEqual(report['tests'], 'PASS')
        self.assertEqual(report['test_methods_reported'], 4)

    def test_tracked_nested_matching_test_blocks_before_execution(self):
        nested = self.root / 'tests' / 'nested'
        nested.mkdir()
        (nested / '__init__.py').write_text('', encoding='utf8')
        (nested / 'test_duo_nested.py').write_text(
            'import unittest\nclass Nested(unittest.TestCase):\n'
            '    def test_nested(self): self.assertTrue(True)\n', encoding='utf8')
        cmd(self.root, 'add', 'tests/nested')
        cmd(self.root, 'commit', '-qm', 'synthetic nested test')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN')
        self.assertIn('pinned allowlist', report['blocker'])

    def test_ignored_nested_matching_test_blocks_before_execution(self):
        nested = self.root / 'tests' / 'hidden'
        nested.mkdir()
        (nested / '__init__.py').write_text('', encoding='utf8')
        (nested / 'test_duo_hidden.py').write_text(
            'import unittest\nclass Hidden(unittest.TestCase):\n'
            '    def test_hidden(self): self.assertTrue(True)\n', encoding='utf8')
        (self.root / '.git/info/exclude').write_text('tests/hidden/\n', encoding='utf8')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN')
        self.assertIn('pinned allowlist', report['blocker'])

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
