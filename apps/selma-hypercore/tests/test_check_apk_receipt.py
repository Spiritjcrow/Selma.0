"""Real temporary-file tests for offline APK content/digest comparison."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_apk_receipt import compare_apk, load_receipt, ReceiptError, CHUNK_BYTES


def receipt(data=b'APK test bytes'):
    return {
        'schema_version': 1, 'source_type': 'owner_import',
        'attestation': 'UNVERIFIED_USER_SUPPLIED',
        'build': {
            'app_id': 'a' * 24, 'build_id': 'b' * 24,
            'commit_sha': 'c' * 40, 'workflow_id': 'selma-android-debug',
            'status': 'failed',
            'artifact': {
                'filename': 'app-debug.apk', 'bytes': len(data),
                'sha256_claimed': hashlib.sha256(data).hexdigest(),
            }
        }
    }


class ApkReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'app-debug.apk'
        self.raw = b'APK test bytes'
        self.path.write_bytes(self.raw)

    def test_matches_actual_local_file_but_not_provider(self):
        result = compare_apk(self.path, receipt(self.raw))
        self.assertEqual(result['outcome'], 'LOCAL_BYTES_MATCH_CLAIM')
        self.assertFalse(result['provider_authenticated'])
        self.assertFalse(result['apk_install_tested'])

    def test_mismatched_bytes_fail(self):
        self.path.write_bytes(b'REPLACED' + self.raw)
        self.assertEqual(compare_apk(self.path, receipt(self.raw))['outcome'], 'MISMATCH')

    def test_mismatched_claimed_size_fails(self):
        claim = receipt(self.raw)
        claim['build']['artifact']['bytes'] += 10
        self.assertEqual(compare_apk(self.path, claim)['outcome'], 'MISMATCH')

    def test_failed_build_never_becomes_approval(self):
        result = compare_apk(self.path, receipt(self.raw))
        self.assertEqual(result['source_attestation'], 'UNVERIFIED_USER_SUPPLIED')

    def test_unknown_secret_fields_rejected(self):
        r = receipt(); r['build']['api_key'] = 'sensitive'
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_unsafe_attestation_rejected(self):
        r = receipt(); r['attestation'] = 'VERIFIED'
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_missing_sha_claim_rejected(self):
        r = receipt(); del r['build']['artifact']['sha256_claimed']
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_wrong_filename_rejected(self):
        r = receipt(); r['build']['artifact']['filename'] = 'other.apk'
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_symlink_file_rejected(self):
        alt = Path(self.tmp.name) / 'linked.apk'; alt.symlink_to(self.path)
        with self.assertRaises(ReceiptError): compare_apk(alt, receipt())

    def test_digest_across_multiple_chunks(self):
        raw = b'Q' * (CHUNK_BYTES * 2 + 7)
        self.path.write_bytes(raw)
        self.assertEqual(compare_apk(self.path, receipt(raw))['outcome'], 'LOCAL_BYTES_MATCH_CLAIM')

    def test_receipt_size_cap(self):
        huge = Path(self.tmp.name) / 'receipt.json'
        huge.write_bytes(b'{' + b'x'*100001)
        with self.assertRaises(ReceiptError): load_receipt(huge)

    def test_malformed_status_type_rejected(self):
        r = receipt(); r['build']['status'] = []
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_spoofed_source_host_rejected(self):
        r = receipt(); r['build']['source_url'] = 'https://codemagic.io.evil.test/app/abc'
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_nested_environment_secret_rejected(self):
        r = receipt(); r['build']['environment'] = {'token': 'sensitive'}
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_bad_timestamp_rejected(self):
        r = receipt(); r['build']['started_utc'] = '2026-11-16T25:90:00Z'
        with self.assertRaises(ReceiptError): compare_apk(self.path, r)

    def test_cli_exit_codes(self):
        path = Path(self.tmp.name) / 'receipt.json'
        path.write_text(json.dumps(receipt(self.raw)))
        script=Path(__file__).resolve().parents[1] / 'tools/check_apk_receipt.py'
        result = subprocess.run([sys.executable, str(script),'--apk',str(self.path),'--receipt',str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['outcome'],'LOCAL_BYTES_MATCH_CLAIM')
        r=receipt(self.raw); r['build']['artifact']['sha256_claimed']='f'*64
        path.write_text(json.dumps(r))
        result = subprocess.run([sys.executable, str(script),'--apk',str(self.path),'--receipt',str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['outcome'],'MISMATCH')

if __name__=='__main__': unittest.main()
