from pathlib import Path
import tempfile, unittest
from selma_data_compiler.compiler import SelmaDataCompiler

class CompilerTests(unittest.TestCase):
    def test_compile_and_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Selma.0"
            (root / "selma_core").mkdir(parents=True)
            (root / "memory").mkdir(); (root / "avatar").mkdir()
            (root / "selma_core" / "main.py").write_text("def boot():\n    return True\n")
            (root / "memory" / "store.py").write_text("class MemoryStore:\n    pass\n")
            (root / "avatar" / "overlay.kt").write_text("class SelmaOverlay {}\n")
            (root / "selma_config.json").write_text('{"local_only": true}')
            out = root / ".compiler-test"
            result = SelmaDataCompiler(out).compile([root])
            domains = result["manifest"]["domains"]
            for domain in ("core", "memory", "avatar", "config"):
                self.assertIn(domain, domains)
            self.assertTrue((out / "catalog.sqlite3").exists())

    def test_conflict_retained(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Selma.0"
            (root / "a" / "memory").mkdir(parents=True); (root / "b" / "memory").mkdir(parents=True)
            (root / "a" / "memory" / "store.py").write_text("VALUE=1\n")
            (root / "b" / "memory" / "store.py").write_text("VALUE=2\n")
            result = SelmaDataCompiler(root / ".compiler-test").compile([root])
            self.assertGreaterEqual(len(result["conflicts"]), 1)

    def test_config_role_beats_content_keyword(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Selma.0"; root.mkdir(parents=True)
            (root / "selma_config.json").write_text('{"audit": true, "local_only": true}')
            result = SelmaDataCompiler(root / ".compiler-test").compile([root])
            self.assertEqual(result["manifest"]["domains"].get("config"), 1)
            self.assertNotIn("safety", result["manifest"]["domains"])

if __name__ == "__main__":
    unittest.main()
