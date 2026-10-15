import unittest
from queue_dry_run import evaluate

class QueueTests(unittest.TestCase):
    def test_first_task_ready(self):
        tasks = evaluate({})
        self.assertEqual([t["id"] for t in tasks if t["status"] == "ready"], ["A1"])

    def test_unblock_after_audit(self):
        tasks = evaluate({"A1": "done"})
        self.assertEqual([t["id"] for t in tasks if t["status"] == "ready"], ["S1", "A2"])

    def test_invalid_completion_fails(self):
        with self.assertRaises(ValueError):
            evaluate({"S1": "done"})

    def test_unknown_task_fails(self):
        with self.assertRaises(ValueError):
            evaluate({"X": "done"})

if __name__ == "__main__":
    unittest.main()
