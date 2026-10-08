import sqlite3
import unittest
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "db"
    / "migrations"
    / "001_coordination_core.sql"
)


class CoordinationCoreMigrationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(MIGRATION.read_text(encoding="utf-8"))

    def tearDown(self):
        self.db.close()

    def test_creates_coordination_tables(self):
        names = {
            row[0]
            for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {"wisdomux_agents", "wisdomux_tasks", "wisdomux_task_dependencies",
             "wisdomux_events"}.issubset(names)
        )

    def test_rejects_task_without_registered_agent(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """
                INSERT INTO wisdomux_tasks
                    (task_id, project_id, title, state, truth_state,
                     claimed_by_agent, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-1", "selma", "Build queue", "CLAIMED", "REAL",
                    "missing-agent", "2026-10-08T04:00:00Z",
                    "2026-10-08T04:00:00Z",
                ),
            )

    def test_events_are_append_only(self):
        self.db.execute(
            """
            INSERT INTO wisdomux_events
                (event_id, project_id, task_id, event_type, truth_state,
                 payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-1", "selma", None, "OBSERVED", "REAL", "{}",
                "2026-10-08T04:00:00Z",
            ),
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.db.execute(
                "UPDATE wisdomux_events SET event_type = 'ALTERED' "
                "WHERE event_id = 'event-1'"
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.db.execute(
                "DELETE FROM wisdomux_events WHERE event_id = 'event-1'"
            )

    def test_migration_is_idempotent(self):
        self.db.executescript(MIGRATION.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
