"""Source-evidence contracts for the multi-host migration inventory."""

import json
from pathlib import Path
import re
import unittest


INVENTORY = (
    Path(__file__).resolve().parents[1]
    / ".migration"
    / "repository-inventory-2026-10-14.json"
)


class MigrationInventoryContracts(unittest.TestCase):
    def test_every_source_has_stable_id_and_default_branch_head(self):
        data = json.loads(INVENTORY.read_text(encoding="utf-8"))
        sources = data["source_repositories"]
        self.assertEqual(len(sources), 12)
        self.assertEqual(sum(item["visibility"] == "private" for item in sources), 5)
        self.assertEqual(sum(item["visibility"] == "public" for item in sources), 7)

        ids = []
        for item in sources:
            repository_id = item.get("source_repository_id")
            head_sha = item.get("source_head_sha")
            with self.subTest(repository=item["name"]):
                self.assertIsInstance(repository_id, int)
                self.assertGreater(repository_id, 0)
                self.assertIsInstance(head_sha, str)
                self.assertRegex(head_sha, re.compile(r"^[0-9a-f]{40}$"))
                self.assertEqual(item["default_branch"], "main")
                self.assertIsNone(item["destination_gitlab_url"])
                self.assertIsNone(item["destination_bitbucket_url"])
            ids.append(repository_id)

        self.assertEqual(len(ids), len(set(ids)))
        selma = next(item for item in sources if item["name"] == "Selma.0")
        self.assertEqual(data["known_refs"]["Selma0_main"], selma["source_head_sha"])


if __name__ == "__main__":
    unittest.main()
