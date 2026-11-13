"""Contracts ensuring the exact-origin regression executes in CI."""

from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "selma-android-build.yml"


class CompanionOriginWorkflowContracts(unittest.TestCase):
    def test_exact_origin_regression_is_compiled_and_run(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        compile_command = (
            "javac -d build/security-tests "
            "app/src/main/java/ai/selma/companion/CompanionOriginPolicy.java "
            "security-tests/CompanionOriginPolicyCheck.java"
        )
        run_command = "java -cp build/security-tests CompanionOriginPolicyCheck"
        self.assertIn("Run companion origin security regression", workflow)
        self.assertIn(compile_command, workflow)
        self.assertIn(run_command, workflow)
        self.assertLess(workflow.index(compile_command), workflow.index(run_command))


if __name__ == "__main__":
    unittest.main()
