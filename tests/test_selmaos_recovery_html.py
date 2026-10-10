"""Static contracts for the standalone, offline SelmaOS recovery desktop."""
from pathlib import Path
import unittest

HTML = Path(__file__).resolve().parents[1] / "sites" / "selmaos" / "selmaos.html"


class SelmaOSBrowserRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")

    def test_no_external_dependency(self):
        for value in ('https://', '<script src=', '<link rel='):
            self.assertNotIn(value, self.html)

    def test_required_ui(self):
        for section in ('home', 'notes', 'reminders', 'focus', 'calculator', 'files'):
            self.assertIn('id="' + section + '"', self.html)

    def test_backup_and_safe_output(self):
        for value in ('id="backup"', 'id="restore"', 'id="secondary"',
                      'localStorage.setItem', 'textContent', 'id="taskList"'):
            self.assertIn(value, self.html)
        self.assertNotIn('eval(', self.html)
        self.assertNotIn('new Function(', self.html)


if __name__ == "__main__":
    unittest.main()
