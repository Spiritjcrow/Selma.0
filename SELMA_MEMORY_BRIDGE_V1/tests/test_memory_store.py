from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_store import MemoryStore


def test_add_deduplicates(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    first, created1 = store.add(source="selma", content="hello", role="user")
    second, created2 = store.add(source="selma", content="hello", role="user")
    assert created1 is True
    assert created2 is False
    assert first.digest == second.digest


def test_search_and_fetch(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    record, _ = store.add(
        source="chatgpt",
        content="Selma offline-first architecture checkpoint",
        role="user",
        created_at="2026-09-06T12:00:00-05:00",
        provenance={"authorization": "test"},
    )
    matches = store.search("offline-first")
    assert [m.record_id for m in matches] == [record.record_id]
    fetched = store.fetch(record.record_id)
    assert fetched is not None
    assert fetched.content == record.content
