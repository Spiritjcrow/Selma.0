"""Test that proposal review is static and requires provenance."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from tools import selma_candidate_forge as forge
from tools import selma_candidate_review as review


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.src = self.root / 'core/example.py'
        self.src.parent.mkdir()
        self.src.write_text('VALUE = 1\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.task = {'base_sha': self.git('rev-parse','HEAD'), 'target': 'core/example.py',
                     'goal': 'Improve the constant value.', 'model': 'fixture'}
        self.proposal = forge.forge(self.root, self.task,
            lambda *args: json.dumps({'target': 'core/example.py', 'replacement': 'VALUE = 2\n'}))
        self.id = self.proposal.name

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root,
                              capture_output=True, text=True, check=True).stdout.strip()

    def test_review_passes_without_changing_source(self):
        report = review.review(self.root, self.id)
        result = json.loads(report.read_text())
        self.assertTrue(result['applies_cleanly'])
        self.assertTrue(result['python_ast_parse_passed'])
        self.assertFalse(result['tests_executed'])
        self.assertEqual('STATIC_OK_HUMAN_REVIEW_REQUIRED', result['status'])
        self.assertEqual('VALUE = 1\n', self.src.read_text())
        self.assertEqual('', self.git('status', '--porcelain'))

    def test_malformed_candidate_id_rejected(self):
        with self.assertRaisesRegex(forge.ForgeError, 'identifier'):
            review.review(self.root, '../evil')

    def test_missing_candidate_rejected(self):
        with self.assertRaisesRegex(forge.ForgeError, 'missing'):
            review.review(self.root, '20261030T123456Z-'+'f'*12)

    def test_source_drift_rejected(self):
        self.src.write_text('VALUE = 3\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'advance')
        with self.assertRaisesRegex(forge.ForgeError, 'mismatched'):
            review.review(self.root, self.id)

    def test_modified_patch_rejected_by_digest(self):
        file = self.proposal.with_suffix('.diff')
        file.write_text(file.read_text().replace('+VALUE = 2', '+VALUE = 3'))
        with self.assertRaisesRegex(forge.ForgeError, 'digest mismatch'):
            review.review(self.root, self.id)

    def test_invalid_python_syntax_rejected(self):
        manifest_file = self.proposal.with_suffix('.json')
        manifest = json.loads(manifest_file.read_text())
        replacement = 'def : broken\n'
        manifest['candidate_sha256'] = review.digest(replacement.encode())
        manifest_file.write_text(json.dumps(manifest))
        self.proposal.with_suffix('.diff').write_text('--- a/core/example.py\n+++ b/core/example.py\n@@ -1 +1 @@\n-VALUE = 1\n+def : broken\n')
        with self.assertRaisesRegex(forge.ForgeError, 'syntax invalid'):
            review.review(self.root, self.id)

    def test_multifile_patch_rejected(self):
        patch = self.proposal.with_suffix('.diff')
        patch.write_text(patch.read_text()+'--- a/core/extra.py\n+++ b/core/extra.py\n')
        with self.assertRaisesRegex(forge.ForgeError, 'multiple files'):
            review.review(self.root, self.id)

    def test_kill_switch_rejected(self):
        forge.git_private(self.root, 'SELMA_BUILD_STOP').touch()
        with self.assertRaisesRegex(forge.ForgeError, 'kill switch'):
            review.review(self.root, self.id)

    def test_bad_manifest_schema_rejected(self):
        file = self.proposal.with_suffix('.json')
        data = json.loads(file.read_text())
        data['extra_action'] = 'execute'
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(forge.ForgeError, 'malformed'):
            review.review(self.root, self.id)


if __name__ == '__main__':
    unittest.main()
