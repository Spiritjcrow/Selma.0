"""Synthetic core API surrogate regression; not independent phone testing."""
from __future__ import annotations

import unittest
from core.duo_handoff import HandoffMessage, validate_exchange


def builder():
    return {
        "schema_version": 1,
        "task_id": "synthetic",
        "repository": "Spiritjcrow/Selma.0",
        "ref": "synthetic/ref",
        "actor_role": "builder",
        "status": "submitted",
        "artifact": "synthetic:artifact",
        "evidence": [],
        "summary": "synthetic only",
    }


class DirectMappingSurrogateTests(unittest.TestCase):
    def test_rejects_unpaired_surrogate_in_task_id(self):
        item = builder()
        item["task_id"] = "bad\ud800"
        with self.assertRaisesRegex(ValueError, "unpaired Unicode surrogate"):
            HandoffMessage.from_mapping(item)

    def test_rejects_unpaired_surrogate_in_tester_evidence(self):
        item = builder()
        item.update(actor_role="tester", status="pass", evidence=["bad\udfff"])
        with self.assertRaisesRegex(ValueError, "unpaired Unicode surrogate"):
            HandoffMessage.from_mapping(item)

    def test_rejects_unpaired_surrogate_in_summary_via_exchange(self):
        item = builder()
        item["summary"] = "bad\udc00"
        with self.assertRaisesRegex(ValueError, "unpaired Unicode surrogate"):
            validate_exchange([item])


if __name__ == "__main__":
    unittest.main()
