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

    def test_ast_parse_only_does_not_misreport_compilation(self):
        # ast.parse accepts a module-level return; compile() rejects it.
        # Syntax evidence must fail before any tests are executed.
        path = self.root / runner.SOURCE_FILES[0]
        path.write_text('return 42\n', encoding='utf8')
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic compile-only syntax failure')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['syntax'], 'FAIL', report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertEqual(report['blocker'], 'pinned Python input failed compilation')

    def test_clean_exact_sha_runs_only_four_tests(self):
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 0, report)
        self.assertEqual(report['tests'], 'PASS')
        self.assertEqual(report['test_methods_reported'], 4)
        self.assertEqual(report['state'], 'REVIEW')

    def test_pinned_test_module_without_methods_blocks(self):
        # A clean commit can remove all methods from one pinned test file.
        # Other modules passing must not conceal the lost coverage.
        (self.root / runner.TEST_FILES[1]).write_text('import unittest\n', encoding='utf8')
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic lost test module')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN')
        self.assertIn('declares no test methods', report['blocker'])

    def test_declared_methods_not_executed_are_incomplete(self):
        # unittest load_tests can suppress a declared test while exiting 0.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Synthetic(unittest.TestCase):\n'
            '    def test_one(self): self.assertTrue(True)\n'
            '    def test_two(self): self.assertTrue(True)\n'
            'def load_tests(loader, tests, pattern):\n'
            '    return loader.loadTestsFromName("Synthetic.test_one", __import__(__name__))\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic hidden declared method')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('defines load_tests', report['blocker'])

    def test_forged_unittest_summary_does_not_inflate_method_count(self):
        # A committed test module can print a fake unittest summary at import
        # time, before the real summary. The runner must not mistake the first
        # arbitrary stderr line for unittest's actual completed test count.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest, sys\n'
            'sys.stderr.write("Ran 999 tests in 0.000s\\n\\nOK\\n")\n'
            'class Synthetic(unittest.TestCase):\n'
            '    def test_one(self): self.assertTrue(True)\n'
            '    def test_two(self): self.assertTrue(True)\n'
            'def load_tests(loader, tests, pattern):\n'
            '    return loader.loadTestsFromName("Synthetic.test_one", __import__(__name__))\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic forged unittest summary')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('defines load_tests', report['blocker'])
        self.assertEqual(report['state'], 'BLOCKED')

    def test_unexpected_dynamic_test_count_is_incomplete(self):
        # A committed load_tests hook can add executable tests outside the
        # declared pinned test-method count. Do not report exact coverage.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Synthetic(unittest.TestCase):\n'
            '    def test_one(self): self.assertTrue(True)\n'
            'def load_tests(loader, tests, pattern):\n'
            '    suite = loader.loadTestsFromTestCase(Synthetic)\n'
            '    suite.addTest(unittest.FunctionTestCase(lambda: None))\n'
            '    return suite\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic extra dynamic test')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('defines load_tests', report['blocker'])
        self.assertEqual(report['state'], 'BLOCKED')

    def test_duplicate_method_substitution_hook_blocks_before_execution(self):
        # Equal executed and declared counts do not establish unique coverage:
        # a load_tests hook could repeat a passing method and omit a failure.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Synthetic(unittest.TestCase):\n'
            '    def test_one(self): self.assertTrue(True)\n'
            '    def test_two(self): self.fail("UNEXECUTED")\n'
            'def load_tests(loader, tests, pattern):\n'
            '    return unittest.TestSuite([Synthetic("test_one"), Synthetic("test_one")])\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic duplicated test method')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('defines load_tests', report['blocker'])
        self.assertEqual(report['state'], 'BLOCKED')

    def test_lambda_load_tests_substitution_blocks_before_execution(self):
        # A module-level lambda assigned to load_tests bypasses a guard that
        # checks only FunctionDef nodes, yet unittest honors the hook.
        # It can repeat a passing method and hide a failing method while
        # preserving the exact reported test count.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Synthetic(unittest.TestCase):\n'
            '    def test_one(self): self.assertTrue(True)\n'
            '    def test_two(self): self.fail("UNEXECUTED")\n'
            'load_tests = lambda loader, tests, pattern: unittest.TestSuite(['
            'Synthetic("test_one"), Synthetic("test_one")])\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic lambda load_tests substitution')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('defines load_tests', report['blocker'])
        self.assertEqual(report['state'], 'BLOCKED')

    def test_module_getattr_cannot_substitute_unittest_suite(self):
        # unittest getattr(module, 'load_tests') invokes a module-level
        # __getattr__ even if no load_tests binding appears in the AST.
        # A hook can repeat a passing method and hide a failing one while
        # preserving the exact declared test count.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Synthetic(unittest.TestCase):\n'
            '    def test_one(self): self.assertTrue(True)\n'
            '    def test_two(self): self.fail("UNEXECUTED")\n'
            'def __getattr__(name):\n'
            '    if name == "load_tests":\n'
            '        return lambda loader, tests, pattern: unittest.TestSuite([Synthetic("test_one"), Synthetic("test_one")])\n'
            '    raise AttributeError(name)\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic module getattr test substitution')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('defines __getattr__', report['blocker'])

    def test_ignored_package_cannot_shadow_pinned_module(self):
        # An ignored package wins Python import resolution over the pinned
        # core/duo_handoff.py, even though Git status and blob hashes match.
        # Without the guard, the unpinned package can satisfy the test and
        # produce a false PASS for code that was never actually imported.
        source = self.root / runner.SOURCE_FILES[0]
        source.write_text('VALUE = "pinned"\n', encoding='utf8')
        test = self.root / runner.TEST_FILES[0]
        test.write_text(
            'import unittest\nfrom core.duo_handoff import VALUE\n'
            'class TestShadow(unittest.TestCase):\n'
            '    def test_ok(self): self.assertEqual(VALUE, "shadow")\n',
            encoding='utf8',
        )
        (self.root / '.gitignore').write_text(
            'tests/test_duo_ignored.py\ncore/duo_handoff/\n', encoding='utf8'
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic pinned module shadow')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        shadow = self.root / 'core' / 'duo_handoff'
        shadow.mkdir()
        (shadow / '__init__.py').write_text('VALUE = "shadow"\n', encoding='utf8')
        self.assertEqual(cmd(self.root, 'status', '--porcelain', '--untracked-files=all'), '')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('package directory shadows pinned module', report['blocker'])

    def test_all_expected_failures_are_incomplete(self):
        # unittest exits zero for suites containing only expected failures.
        # Such a suite has not demonstrated any successful assertions.
        for path in runner.TEST_FILES:
            (self.root / path).write_text(
                'import unittest\n'
                'class Synthetic(unittest.TestCase):\n'
                '    @unittest.expectedFailure\n'
                '    def test_known_failure(self):\n'
                '        self.assertEqual(1, 2)\n',
                encoding='utf8',
            )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic expected-failure suite')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'INCOMPLETE', report)
        self.assertEqual(report['test_methods_reported'], 4)
        self.assertEqual(report['test_methods_expected_failures'], 4)
        self.assertEqual(report['state'], 'BLOCKED')

    def test_partial_expected_failures_are_incomplete(self):
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Synthetic(unittest.TestCase):\n'
            '    @unittest.expectedFailure\n'
            '    def test_known_failure(self):\n'
            '        self.assertEqual(1, 2)\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic mixed expected-failure suite')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'INCOMPLETE', report)
        self.assertEqual(report['test_methods_reported'], 4)
        self.assertEqual(report['test_methods_expected_failures'], 1)
        self.assertEqual(report['state'], 'BLOCKED')

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

    def test_non_testcase_method_and_alias_cannot_inflate_pass_count(self):
        # A helper with a test_-named method is not collected by unittest.
        # Repeating a passing TestCase under a module alias can make the old
        # AST-all-functions count match the reported count despite the omission.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class HiddenHelper:\n'
            '    def test_should_fail(self): raise AssertionError("OMITTED")\n'
            'class TestGood(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'GoodAlias = TestGood\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic non-TestCase alias inflation')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'INCOMPLETE', report)
        self.assertEqual(report['test_methods_declared'], 4, report)
        self.assertEqual(report['test_methods_reported'], 5, report)
        self.assertEqual(report['state'], 'BLOCKED', report)

    def test_nested_testcase_and_alias_cannot_inflate_pass_count(self):
        # unittest does not discover nested TestCase classes. The old AST
        # walker counted one hidden method while a top-level alias duplicated
        # a passing method, allowing a false PASS at the expected count.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class TestGood(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'class HiddenNamespace:\n'
            '    class TestNeverLoaded(unittest.TestCase):\n'
            '        def test_hidden_failure(self): self.fail("OMITTED")\n'
            'GoodAlias = TestGood\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic nested TestCase alias inflation')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'INCOMPLETE', report)
        self.assertEqual(report['test_methods_declared'], 4, report)
        self.assertEqual(report['test_methods_reported'], 5, report)
        self.assertEqual(report['state'], 'BLOCKED', report)

    def test_deleted_testcase_class_cannot_be_hidden_by_passing_alias(self):
        # A deleted failing top-level class is still counted by AST, but
        # unittest cannot discover it. Aliasing the passing class conceals
        # the omission unless module binding changes are rejected.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Visible(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'class Hidden(unittest.TestCase):\n'
            '    def test_failure(self): self.fail("UNEXECUTED")\n'
            'del Hidden\n'
            'VisibleAlias = Visible\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic deleted TestCase and alias')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('TestCase binding changed', report['blocker'])

    def test_rebound_testcase_class_cannot_be_hidden_by_passing_alias(self):
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Visible(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'class Hidden(unittest.TestCase):\n'
            '    def test_failure(self): self.fail("UNEXECUTED")\n'
            'Hidden = None\n'
            'VisibleAlias = Visible\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic rebound TestCase and alias')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('TestCase binding changed', report['blocker'])

    def test_conditional_deleted_testcase_cannot_be_hidden_by_alias(self):
        # A top-level conditional executes before unittest discovery. The
        # deleted failing class must not be offset by a passing-class alias.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Visible(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'class Hidden(unittest.TestCase):\n'
            '    def test_failure(self): self.fail("UNEXECUTED")\n'
            'if True:\n'
            '    del Hidden\n'
            'VisibleAlias = Visible\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic conditional deleted TestCase')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('TestCase binding changed', report['blocker'])

    def test_conditional_rebound_testcase_cannot_be_hidden_by_alias(self):
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Visible(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'class Hidden(unittest.TestCase):\n'
            '    def test_failure(self): self.fail("UNEXECUTED")\n'
            'if True:\n'
            '    Hidden = None\n'
            'VisibleAlias = Visible\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic conditional rebound TestCase')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('TestCase binding changed', report['blocker'])

    def test_conditional_function_definition_cannot_hide_failing_testcase(self):
        # Defining a function inside a module-level conditional rebinds a
        # failing TestCase class without any ast.Name(Store) node.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class Visible(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'class Hidden(unittest.TestCase):\n'
            '    def test_failure(self): self.fail("UNEXECUTED")\n'
            'if True:\n'
            '    def Hidden(): return None\n'
            'VisibleAlias = Visible\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic conditional function rebinding')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertIn('TestCase binding changed', report['blocker'])

    def test_module_dir_hook_cannot_hide_failing_test_with_alias(self):
        # unittest uses dir(module) to discover TestCase classes. A custom
        # __dir__ can hide a failing class and list a passing class twice,
        # keeping the declared/reported test counts equal.
        path = self.root / runner.TEST_FILES[0]
        path.write_text(
            'import unittest\n'
            'class TestGood(unittest.TestCase):\n'
            '    def test_ok(self): self.assertTrue(True)\n'
            'class TestBad(unittest.TestCase):\n'
            '    def test_should_fail(self): self.fail("HIDDEN_FAILURE")\n'
            'GoodAlias = TestGood\n'
            'def __dir__():\n'
            '    return ["TestGood", "GoodAlias"]\n',
            encoding='utf8',
        )
        cmd(self.root, 'add', '.')
        cmd(self.root, 'commit', '-qm', 'synthetic module __dir__ test substitution')
        self.sha = cmd(self.root, 'rev-parse', 'HEAD')
        report, exit_code = self.verify()
        self.assertEqual(exit_code, 2, report)
        self.assertEqual(report['tests'], 'NOT_RUN', report)
        self.assertEqual(report['state'], 'BLOCKED', report)
        self.assertIn('defines __dir__', report['blocker'])

if __name__ == '__main__':
    unittest.main()
