"""Fail-closed Gradle log classification tests. No cloud CI needed."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from classify_gradle_log import classify, from_file, LogError, MAX_BYTES


class GradleLogTests(unittest.TestCase):
    def test_success_with_observed_tasks(self):
        report=classify('''> Task :app:lintDebug\n> Task :app:testDebugUnitTest\n> Task :app:assembleDebug\nBUILD SUCCESSFUL in 52s\n''')
        self.assertEqual(report['overall'], 'REPORTED_SUCCESSFUL')
        self.assertEqual(len(report['tasks']), 3)
        self.assertEqual(report['tasks'][':app:assembleDebug'],'REPORTED_EXECUTED_IN_SUCCESSFUL_BUILD')
        self.assertFalse(report['authenticated_runner'])

    def test_failed_task_is_not_success(self):
        report=classify('> Task :app:lintDebug FAILED\nBUILD FAILED in 4s')
        self.assertEqual(report['overall'], 'REPORTED_FAILED')
        self.assertEqual(report['tasks'][':app:lintDebug'],'REPORTED_FAILED')

    def test_missing_tests_not_assumed_run(self):
        report=classify('> Task :app:assembleDebug\nBUILD SUCCESSFUL')
        self.assertEqual(report['tasks'][':app:testDebugUnitTest'],'NOT_OBSERVED')

    def test_cached_is_not_executed(self):
        report=classify('> Task :app:testDebugUnitTest UP-TO-DATE\nBUILD SUCCESSFUL')
        self.assertEqual(report['tasks'][':app:testDebugUnitTest'],'REPORTED_REUSED')

    def test_missing_end_marker_is_inconclusive(self):
        report=classify('> Task :app:assembleDebug')
        self.assertEqual(report['overall'],'INCOMPLETE_OR_UNKNOWN')
        self.assertEqual(report['tasks'][':app:assembleDebug'],'REPORTED_EXECUTED_NO_RESULT')

    def test_ansi_escapes_ignored(self):
        report=classify('\x1b[32m> Task :app:lintDebug\x1b[0m\nBUILD SUCCESSFUL')
        self.assertEqual(report['tasks'][':app:lintDebug'],'REPORTED_EXECUTED_IN_SUCCESSFUL_BUILD')

    def test_sensitive_log_lines_never_echoed(self):
        report=classify('password=SECRET_DO_NOT_ECHO\nBUILD FAILED')
        self.assertNotIn('SECRET_DO_NOT_ECHO',json.dumps(report))

    def test_log_size_cap(self):
        with self.assertRaises(LogError): classify('a'*(MAX_BYTES+1))

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'a.log';source.write_text('BUILD SUCCESSFUL')
            linked=Path(d)/'link.log';linked.symlink_to(source)
            with self.assertRaises(LogError): from_file(linked)

    def test_cli_failure_exit(self):
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/'b.log';log.write_text('BUILD FAILED')
            script=Path(__file__).resolve().parents[1]/'tools/classify_gradle_log.py'
            proc=subprocess.run([sys.executable,str(script),str(log)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,1)
            self.assertEqual(json.loads(proc.stdout)['overall'],'REPORTED_FAILED')

if __name__=='__main__': unittest.main()
