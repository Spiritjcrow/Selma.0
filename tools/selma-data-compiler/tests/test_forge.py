from pathlib import Path
import tempfile, unittest
from selma_data_compiler.config import ForgeConfig
from selma_data_compiler.forge import SelmaForge
from selma_data_compiler.policy import CapabilityBroker, ActionMode
from selma_data_compiler.sandbox import VirtualSandbox

class ForgeTests(unittest.TestCase):
    def test_forge_generates_snapshot_and_resolved_config(self):
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
            self.assertTrue((forge_dir / "resolved_config.json").exists())
            self.assertIn("config_sources", result["snapshot"])

    def test_workspace_config_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Selma.0"
            (root / ".selma").mkdir(parents=True)
            (root / ".selma" / "forge_config.toml").write_text("[policy]\nmax_questions_before_best_effort = 0\n[sandbox]\ntimeout_seconds = 7\n")
            config = ForgeConfig.load(root)
            self.assertEqual(config.max_questions, 0)
            self.assertEqual(config.sandbox_timeout_seconds, 7)

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
