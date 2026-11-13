import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'echocopy_worker.py'
spec = importlib.util.spec_from_file_location('echocopy_worker', SCRIPT)
echo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(echo)

class EchoCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_uninitialized_status_is_not_pass(self):
        with echo.connect(self.root) as con:
            s = echo.last_status(con)
        self.assertEqual('NOT_RUN', s['last_result'])
        self.assertFalse(s['independent_tester_verified'])

    def test_good_commit_and_drift(self):
        good = subprocess.CompletedProcess([], 0, echo.EXPECTED + '\n')
        with patch.object(echo.subprocess, 'run', return_value=good) as call:
            status, sha, _ = echo.query_pr()
            self.assertEqual((status, sha), ('UNCHANGED', echo.EXPECTED))
            self.assertEqual(call.call_args.args[0][:2], ['gh', 'api'])
        bad = subprocess.CompletedProcess([], 0, 'a' * 40 + '\n')
        with patch.object(echo.subprocess, 'run', return_value=bad):
            self.assertEqual('CHANGED', echo.query_pr()[0])

    def test_failed_network_does_not_claim_success(self):
        with patch.object(echo.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '')):
            self.assertEqual('BLOCKED', echo.query_pr()[0])
        with patch.object(echo.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual('BLOCKED', echo.query_pr()[0])

    def test_records_and_bounded_retention(self):
        with echo.connect(self.root) as con:
            for i in range(510):
                echo.record(con, 'UNCHANGED', echo.EXPECTED, 'checked')
            self.assertEqual(500, echo.last_status(con)['checks_recorded'])

    def test_report_and_stop_switch(self):
        report = self.root / 'sd' / 'report.json'
        with patch.object(echo, 'query_pr', return_value=('UNCHANGED', echo.EXPECTED, 'ok')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, echo.main(['once', '--state-dir', str(self.root), '--report', str(report)]))
        data = json.loads(report.read_text())
        self.assertEqual('UNCHANGED', data['result'])
        self.assertFalse(data['apk_verified'])
        with contextlib.redirect_stdout(io.StringIO()):
            echo.main(['stop', '--state-dir', str(self.root)])
            self.assertEqual(2, echo.main(['once', '--state-dir', str(self.root)]))
            echo.main(['resume', '--state-dir', str(self.root)])
        self.assertFalse((self.root / 'STOP').exists())

if __name__ == '__main__':
    unittest.main()
