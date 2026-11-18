import os
import tempfile
import unittest

from selma0_memory_android_v1 import Selma0MemoryAndroidV1


class Selma0MemoryAndroidV1Test(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(handle)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db_path + suffix)
            except FileNotFoundError:
                pass

    def _exercise_retrieval(self, enable_fts):
        memory = Selma0MemoryAndroidV1(self.db_path, enable_fts=enable_fts)
        self.addCleanup(memory.close)
        memory.add("user", "The emergency guardian contact is stored only on this phone.")
        memory.add("assistant", "The basil plant should be watered on Tuesday.")
        memory.add("user", "The local llama model is a small GGUF file.")

        results = memory.search("guardian contact phone", limit=2)

        self.assertTrue(results)
        self.assertIn("guardian contact", results[0]["content"])
        self.assertLessEqual(len(results), 2)
        self.assertIn("score", results[0])

    def test_retrieves_with_available_mode(self):
        self._exercise_retrieval(enable_fts=True)

    def test_retrieves_with_bounded_fallback(self):
        self._exercise_retrieval(enable_fts=False)

    def test_clear_removes_events_and_index_entries(self):
        memory = Selma0MemoryAndroidV1(self.db_path)
        self.addCleanup(memory.close)
        memory.add("user", "Remember the blue notebook.")
        self.assertTrue(memory.search("blue notebook"))

        memory.clear()

        self.assertEqual([], memory.recent())
        self.assertEqual([], memory.search("blue notebook"))


if __name__ == "__main__":
    unittest.main()
