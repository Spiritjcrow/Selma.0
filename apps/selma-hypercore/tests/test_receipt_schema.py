"""Build receipt contract verification. Requires jsonschema for this isolated test, not product runtime."""
import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'assets/build-receipt.schema.json').read_text(encoding='utf-8'))
VALID = {
    'schema_version': 1,
    'source_type': 'owner_import',
    'attestation': 'UNVERIFIED_USER_SUPPLIED',
    'build': {
        'app_id': 'a' * 24,
        'build_id': 'b' * 24,
        'workflow_id': 'selma-android-debug',
        'commit_sha': 'c' * 40,
        'status': 'failed'
    },
}

class ReceiptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Draft202012Validator.check_schema(SCHEMA)
        cls.validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

    def rejects(self, modified):
        self.assertFalse(self.validator.is_valid(modified))

    def test_explicit_failed_build_is_valid_claim_only(self):
        self.assertTrue(self.validator.is_valid(VALID))
        self.assertEqual(VALID['attestation'], 'UNVERIFIED_USER_SUPPLIED')

    def test_rejects_missing_sha(self):
        wrong = copy.deepcopy(VALID); del wrong['build']['commit_sha']; self.rejects(wrong)

    def test_rejects_fake_sha(self):
        wrong = copy.deepcopy(VALID); wrong['build']['commit_sha']='NOT_A_SHA'; self.rejects(wrong)

    def test_rejects_secret_fields(self):
        wrong = copy.deepcopy(VALID); wrong['api_key']='private'; self.rejects(wrong)
        wrong = copy.deepcopy(VALID); wrong['build']['access_token']='private'; self.rejects(wrong)

    def test_rejects_self_authorized_verification(self):
        wrong = copy.deepcopy(VALID); wrong['attestation']='VERIFIED'; self.rejects(wrong)

    def test_rejects_fake_artifact_size(self):
        wrong = copy.deepcopy(VALID); wrong['build']['artifact']={'filename':'app-debug.apk','bytes':0}; self.rejects(wrong)

    def test_rejects_invalid_codema_gic_uri(self):
        wrong = copy.deepcopy(VALID); wrong['build']['source_url']='https://example.com/other'; self.rejects(wrong)

    def test_rejects_invalid_timestamp(self):
        wrong = copy.deepcopy(VALID); wrong['build']['started_utc']='yesterday'; self.rejects(wrong)

    def test_supports_optional_artifact_digest_without_attesting_it(self):
        ok = copy.deepcopy(VALID)
        ok['build']['artifact']={'filename':'app-debug.apk','bytes':10240,'sha256_claimed':'d'*64}
        self.assertTrue(self.validator.is_valid(ok))
        self.assertEqual(ok['attestation'],'UNVERIFIED_USER_SUPPLIED')

if __name__=='__main__': unittest.main()
