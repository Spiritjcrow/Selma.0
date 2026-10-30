"""Offline fixture tests for the review-only local candidate worker."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent.parent / 'tools' / 'selma_candidate_forge.py'
spec = importlib.util.spec_from_file_location('forge', SOURCE)
forge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forge)


class ForgeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.run_git('init', '-q')
        self.run_git('config', 'user.email', 'fixture@example.invalid')
        self.run_git('config', 'user.name', 'Fixture')
        self.code = self.root / 'core/hello.py'
        self.code.parent.mkdir()
        self.code.write_text('VALUE = 1\n', encoding='utf-8')
        self.run_git('add', '.')
        self.run_git('commit', '-qm', 'baseline')
        self.base = self.run_git('rev-parse', 'HEAD')
        self.task = {'base_sha': self.base, 'target': 'core/hello.py',
                     'goal': 'Update the constant to value two.', 'model': 'test-local'}

    def run_git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, text=True,
                              capture_output=True, check=True).stdout.strip()

    def fake(self, content='VALUE = 2\n'):
        return lambda *args: json.dumps({'target': self.task['target'], 'replacement': content})

    def test_valid_review_only_candidate(self):
        prefix = forge.forge(self.root, self.task, self.fake())
        self.assertEqual('VALUE = 1\n', self.code.read_text())
        self.assertEqual(self.base, self.run_git('rev-parse', 'HEAD'))
        self.assertEqual('', self.run_git('status', '--porcelain'))
        self.assertIn('+VALUE = 2', prefix.with_suffix('.diff').read_text())
        self.assertEqual('REVIEW_ONLY_NOT_EXECUTED', json.loads(prefix.with_suffix('.json').read_text())['status'])

    def test_dirty_checkout_rejected(self):
        self.code.write_text('VALUE = 3\n')
        with self.assertRaisesRegex(forge.ForgeError, 'not clean'):
            forge.forge(self.root, self.task, self.fake())

    def test_wrong_base_rejected(self):
        self.task['base_sha'] = 'f' * 40
        with self.assertRaisesRegex(forge.ForgeError, 'base SHA mismatch'):
            forge.forge(self.root, self.task, self.fake())

    def test_stale_path_traversal_rejected(self):
        for path in ('../outside.py', 'core/../secret.py', '/tmp/evil.py', 'core\\evil.py', '.github/workflows/check.yml'):
            with self.subTest(path=path), self.assertRaises(forge.ForgeError):
                forge.validate_target(self.root, path)

    def test_rejects_secret_source(self):
        self.code.write_text('token="ghp_abc"\n')
        self.run_git('add', '.')
        self.run_git('commit', '-qm', 'secret-fake')
        self.task['base_sha'] = self.run_git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(forge.ForgeError, 'credentials'):
            forge.forge(self.root, self.task, self.fake())

    def test_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError):
            forge.decode_json('{"target":"core/hello.py", "target":"core/evil.py", "replacement":"bad"}')

    def test_model_target_mismatch_rejected(self):
        bad = lambda *args: json.dumps({'target':'core/other.py','replacement':'hello'})
        with self.assertRaisesRegex(forge.ForgeError, 'target mismatch'):
            forge.forge(self.root, self.task, bad)

    def test_empty_or_identical_candidate_rejected(self):
        for content in ('', 'VALUE = 1\n'):
            with self.subTest(content=content), self.assertRaises(forge.ForgeError):
                forge.forge(self.root, self.task, self.fake(content))

    def test_invalid_schema_rejected(self):
        bad = lambda *args: json.dumps({'target':'core/hello.py', 'replacement':'hi', 'command':'rm -rf'})
        with self.assertRaisesRegex(forge.ForgeError, 'schema'):
            forge.forge(self.root, self.task, bad)

    def test_stop_switch_prevents_generation(self):
        stop = forge.git_private(self.root, 'SELMA_BUILD_STOP')
        stop.touch()
        with self.assertRaisesRegex(forge.ForgeError, 'stop switch'):
            forge.forge(self.root, self.task, self.fake())

    def test_source_mutated_while_generating(self):
        def mutate(*args):
            self.code.write_text('VALUE = 99\n')
            return self.fake()()
        with self.assertRaisesRegex(forge.ForgeError, 'not clean'):
            forge.forge(self.root, self.task, mutate)

    def test_symlink_target_rejected(self):
        (self.root/'core/link.py').symlink_to(self.code)
        with self.assertRaises(forge.ForgeError):
            forge.validate_target(self.root, 'core/link.py')

    def test_no_redirect_to_external_endpoint(self):
        guard = forge.NoRedirect()
        with self.assertRaisesRegex(forge.ForgeError, "redirect rejected"):
            guard.redirect_request(None, None, 307, "redirect", {}, "https://evil.example")

    def test_no_network_when_using_stub(self):
        def assert_injected(model, goal, target, source):
            self.assertEqual('test-local', model)
            self.assertEqual('core/hello.py', target)
            return json.dumps({'target':target, 'replacement':'VALUE = 2\n'})
        forge.forge(self.root, self.task, assert_injected)


if __name__ == '__main__':
    unittest.main()
