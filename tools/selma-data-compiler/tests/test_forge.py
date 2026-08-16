from pathlib import Path
import tempfile, unittest
from selma_data_compiler.forge import SelmaForge
from selma_data_compiler.policy import CapabilityBroker, ActionMode
from selma_data_compiler.sandbox import VirtualSandbox

class ForgeTests(unittest.TestCase):
    def test_forge_generates_snapshot_and_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Selma.0"
            (root / "selma_core").mkdir(parents=True)
            (root / "voice").mkdir()
            (root / "selma_core" / "main.py").write_text("def boot(): return True\n")
            (root / "voice" / "wakeword.py").write_text("WAKE='selma'\n")
            result = SelmaForge(root).run()
            forge_dir = root / ".selma" / "forge"
            self.assertTrue((forge_dir / "forge_snapshot.json").exists())
            self.assertTrue((forge_dir / "events.jsonl").exists())
            self.assertGreaterEqual(result["snapshot"]["need_count"], 1)

    def test_policy_attempt_first(self):
        broker = CapabilityBroker()
        self.assertEqual(broker.decide("scan").mode, ActionMode.EXECUTE)
        self.assertEqual(broker.decide("unknown-danger", safety_blocked=True).mode, ActionMode.BLOCKED)

    def test_sandbox_runs(self):
        result = VirtualSandbox(timeout_seconds=5).run([__import__("sys").executable, "-c", "print('selma-ok')"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("selma-ok", result.stdout)

if __name__ == "__main__":
    unittest.main()
