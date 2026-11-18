"""Deterministic, network-free tests for EarthWatch input review."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from core.earthwatch import review_snapshot, MAX_JSON_BYTES
from tools.earthwatch_review import run

NOW = datetime(2026, 10, 13, 16, 0, tzinfo=timezone.utc)


def example(**kwargs):
    item = {
        "source_record_id": "alert-1",
        "source_url": "https://example.org/observations/1",
        "category": "air_quality",
        "place": "Example City",
        "observed_at": "2026-10-13T15:00:00Z",
        "reported_severity": "warning",
        "summary": "A reported condition, not a validated measurement",
    }
    item.update(kwargs)
    return item


def snapshot(*records):
    return {"schema_version": 1, "observations": list(records)}


class EarthWatchTests(unittest.TestCase):
    def test_current_is_still_unverified(self):
        result = review_snapshot(snapshot(example()), now=NOW)
        self.assertEqual(result["total"], 1)
        record = result["observations"][0]
        self.assertEqual(record["review_state"], "current_unverified")
        self.assertIs(record["source_verified"], False)
        self.assertFalse(result["sent_notifications"])
        self.assertFalse(result["collected_live_data"])
        self.assertEqual(len(record["content_sha256"]), 64)

    def test_time_windows_by_category(self):
        report = review_snapshot(snapshot(
            example(observed_at="2026-10-09T00:00:00Z"),
            example(source_record_id="housing-1", category="housing",
                    observed_at="2026-10-09T00:00:00Z")), now=NOW)
        states = {r["category"]: r["review_state"] for r in report["observations"]}
        self.assertEqual(states["air_quality"], "stale_unverified")
        self.assertEqual(states["housing"], "current_unverified")

    def test_future_does_not_become_alert(self):
        r = review_snapshot(snapshot(example(observed_at="2026-10-14T16:00:00Z")), now=NOW)
        self.assertEqual(r["observations"][0]["review_state"], "future_timestamp_unverified")

    def test_exact_duplicates_collapse_but_conflicts_fail(self):
        a = example()
        self.assertEqual(review_snapshot(snapshot(a, deepcopy(a)), now=NOW)["total"], 1)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            review_snapshot(snapshot(a, example(summary="changed")), now=NOW)

    def test_bad_links_dates_categories_fail_closed(self):
        for changed in (
            {"source_url": "http://example.org/1"},
            {"source_url": "https://example.org/1?token=secret"},
            {"source_url": "https://127.0.0.1/private"},
            {"observed_at": "2026-10-13T15:00:00"},
            {"category": "secret_surveillance"},
            {"summary": "\x00unsafe"},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                review_snapshot(snapshot(example(**changed)), now=NOW)

    def test_reject_unexpected_schema_and_record_fields(self):
        for invalid in (snapshot(example(extra="hidden")),
                        {"schema_version": True, "observations": []},
                        {"schema_version": 1, "observations": "not an array"}):
            with self.assertRaises(ValueError):
                review_snapshot(invalid, now=NOW)

    def test_cli_uses_local_file_and_size_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            path.write_text(json.dumps(snapshot(example())), encoding="utf-8")
            self.assertEqual(run(path)["total"], 1)
            path.write_bytes(b"X" * (MAX_JSON_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "maximum size"):
                run(path)

    def test_now_requires_timezone(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            review_snapshot(snapshot(example()), now=datetime(2026, 10, 13))


if __name__ == "__main__":
    unittest.main()
