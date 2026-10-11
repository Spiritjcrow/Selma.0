"""First-run source regression: persistence follows runtime preflight and spawn."""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "selma0_first_run_android_v1.py"

class FirstRunOrderTest(unittest.TestCase):
    def test_runtime_preflight_and_spawn_before_save(self):
        text = SOURCE.read_text(encoding="utf-8")
        start = text.index("def do_POST(self):")
        body = text[start:text.index("def main():", start)]
        validate = body.index("profile = checked_preferences(opts)")
        preflight = body.index("if not RUNTIME.is_file():")
        spawn = body.index("subprocess.Popen(")
        save = body.index("save_preferences(opts)")
        self.assertLess(validate, preflight)
        self.assertLess(preflight, spawn)
        self.assertLess(spawn, save)
        self.assertIn("configuration was not saved", body)

if __name__ == "__main__":
    unittest.main()
