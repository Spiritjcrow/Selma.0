"""Pure stdlib tests for the offline read-only queue planner."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.queue_planner import plan, validate


def item(n, state="DISCOVERED", priority="P1", group=None):
    return {
        "task_id": f"test-{n}",
        "priority": priority,
        "planning_state": state,
        "operation": "READ_ONLY_TRIAGE",
        "approval_to_mutate": False,
        "source_url": f"https://example.invalid/issues/{n}",
        "conflict_group": group or f"test-{n}",
        "lane": "review",
        "next_action": "Read current source and report evidence.",
    }


def manifest(*items):
    return {"schema_version": 1, "items": list(items)}


class PlannerTests(unittest.TestCase):
    def test_limit_seven(self):
        result = plan(manifest(*(item(i) for i in range(20))))
        self.assertEqual(len(result["selected"]), 7)
        self.assertEqual(result["actually_executed"], 0)
        self.assertEqual(result["mode"], "READ_ONLY_DRY_RUN")

    def test_next_batch(self):
        data = manifest(*(item(i) for i in range(15)))
        self.assertEqual(plan(data, batch=1)["selected"][0]["task_id"], "test-7")
        self.assertEqual(len(plan(data, batch=2)["selected"]), 1)

    def test_stable_digest(self):
        data = manifest(item(1), item(2))
        self.assertEqual(plan(data)["selection_sha256"], plan(data)["selection_sha256"])

    def test_highest_priority_first(self):
        data = manifest(item(1, priority="P2"), item(2, priority="P0"))
        self.assertEqual(plan(data)["selected"][0]["task_id"], "test-2")

    def test_blocked_and_reserved_excluded(self):
        data = manifest(item(1, state="BLOCKED"), item(2, state="RESERVED_SOL_RED"), item(3))
        result = plan(data)
        self.assertEqual([x["task_id"] for x in result["selected"]], ["test-3"])
        self.assertEqual(result["blocked_or_reserved"], 2)

    def test_conflict_is_deferred(self):
        data = manifest(item(1, group="one"), item(2, group="one"), item(3, group="three"))
        result = plan(data)
        self.assertEqual(len(result["selected"]), 2)
        self.assertEqual(result["deferred_same_conflict_group"], ["test-2"])

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            validate(manifest(item(1), item(1)))

    def test_fail_closed_on_mutation(self):
        entry = item(1)
        entry["operation"] = "DEPLOY"
        with self.assertRaises(ValueError):
            plan(manifest(entry))

    def test_fail_closed_on_approval(self):
        entry = item(1)
        entry["approval_to_mutate"] = True
        with self.assertRaises(ValueError):
            plan(manifest(entry))

    def test_limit_bounds(self):
        with self.assertRaises(ValueError):
            plan(manifest(item(1)), limit=8)
        with self.assertRaises(ValueError):
            plan(manifest(item(1)), batch=-1)

    def test_fail_closed_on_non_https_source(self):
        entry = item(1)
        entry["source_url"] = "file:///etc/passwd"
        with self.assertRaises(ValueError):
            plan(manifest(entry))


if __name__ == "__main__":
    unittest.main()
