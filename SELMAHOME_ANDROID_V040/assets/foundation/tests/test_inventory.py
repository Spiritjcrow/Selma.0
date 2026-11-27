import hashlib
import tempfile
import unittest
from pathlib import Path
from selma_project.__main__ import inventory


class InventoryTests(unittest.TestCase):
    def test_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "main.py").write_bytes(b"pass")
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("private")
            self.assertEqual(inventory(root), {"main.py": hashlib.sha256(b"pass").hexdigest()})

    def test_missing_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                inventory(Path(temp) / "missing")
