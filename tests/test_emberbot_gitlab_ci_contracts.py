"""Contracts for portable EmberBot GitLab APK artifacts."""

from pathlib import Path
import unittest


PIPELINE = Path(__file__).resolve().parents[1] / ".gitlab-ci.yml"


class EmberBotGitLabCiContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = PIPELINE.read_text(encoding="utf-8")

    def test_apk_checksum_sidecar_is_created_uploaded_and_verified(self):
        create = 'sha256sum "$(basename "$APK")" > "$(basename "$APK").sha256"'
        upload = "- EmberBot/bin/*.apk.sha256"
        verify = 'sha256sum --check "$(basename "$file").sha256"'
        self.assertIn(create, self.pipeline)
        self.assertIn(upload, self.pipeline)
        self.assertIn(verify, self.pipeline)
        self.assertLess(self.pipeline.index(create), self.pipeline.index(upload))
        self.assertLess(self.pipeline.index(upload), self.pipeline.index(verify))


if __name__ == "__main__":
    unittest.main()
