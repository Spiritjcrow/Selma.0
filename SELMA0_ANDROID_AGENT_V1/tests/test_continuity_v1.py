#!/usr/bin/env python3
"""Offline regression tests for Selma's text/voice logical-instance identity."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import selma0_runtime_android_v1 as runtime
from selma0_continuity_android_v1 import (
    Selma0ContinuityAndroidV1,
    provider_fingerprint,
)
from selma0_llm_router_android_v1 import Selma0LLMRouterAndroidV1
from selma0_memory_android_v1 import Selma0MemoryAndroidV1


class FakeRouter:
    local_base = "http://127.0.0.1:8080/v1"
    local_model = "test-immutable"
    online_base = "https://unused.invalid/v1"
    online_model = "other-model"

    def __init__(self):
        self.calls = []

    def provider_fingerprint(self, route):
        if route == "offline-local":
            return provider_fingerprint(route, self.local_base, self.local_model)
        return provider_fingerprint(route, self.online_base, self.online_model)

    def reply(self, messages, locked_route=None):
        self.calls.append((list(messages), locked_route))
        text = next(
            item["content"] for item in reversed(messages)
            if item["role"] == "user"
        )
        return {"text": "echo:" + text, "route": "offline-local", "error": None}


class ContinuityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "selma.sqlite3")
        self.memory = Selma0MemoryAndroidV1(db_path=self.db_path)
        self.continuity = Selma0ContinuityAndroidV1(self.memory)
        self.router = FakeRouter()
        self.patches = [
            patch.object(runtime, "MEMORY_V1", self.memory),
            patch.object(runtime, "CONTINUITY_V1", self.continuity),
            patch.object(runtime, "ROUTER_V1", self.router),
        ]
        for item in self.patches:
            item.start()
        self.instance = runtime.Selma0RuntimeAndroidV1()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.memory.conn.close()
        self.temp.cleanup()

    def test_text_voice_text_are_one_identity_and_thread(self):
        turns = [
            self.instance.chat("hello", "text"),
            self.instance.chat("continued by microphone", "voice"),
            self.instance.chat("back to keyboard", "text"),
        ]
        self.assertEqual(
            len({turn["continuity"]["identity_id"] for turn in turns}), 1
        )
        self.assertEqual(len({turn["continuity"]["thread_id"] for turn in turns}), 1)
        self.assertEqual([turn["modality"] for turn in turns],
                         ["text", "voice", "text"])
        self.assertEqual([row["metadata"]["modality"]
                          for row in self.memory.recent(20)],
                         ["text", "text", "voice", "voice", "text", "text"])
        self.assertEqual(len(self.continuity.conversation_history()), 6)
        self.assertEqual(self.router.calls[1][1], "offline-local")
        self.assertTrue(any(
            item["content"] == "hello"
            for item in self.router.calls[1][0]
        ))

    def test_restart_retains_identity_and_archived_events(self):
        self.instance.chat("before restart", "voice")
        before = self.continuity.current()
        second_connection = Selma0MemoryAndroidV1(db_path=self.db_path)
        try:
            second = Selma0ContinuityAndroidV1(second_connection)
            self.assertEqual(second.current(), before)
            self.assertEqual(len(second.conversation_history()), 2)
        finally:
            second_connection.conn.close()

    def test_refresh_preserves_identity_and_archive(self):
        before = self.instance.chat("first", "text")["continuity"]
        after = self.instance.refresh_context()
        self.assertEqual(after["identity_id"], before["identity_id"])
        self.assertEqual(after["thread_id"], before["thread_id"])
        self.assertEqual(after["context_generation"], 1)
        self.assertIsNone(after["locked_route"])
        self.instance.chat("second", "voice")
        self.assertEqual(len(self.continuity.conversation_history()), 2)
        self.assertEqual(len(self.memory.recent(20)), 4)

    def test_changed_model_is_rejected_before_new_event(self):
        self.instance.chat("first", "text")
        self.router.local_model = "changed-model"
        with self.assertRaisesRegex(RuntimeError, "configured model changed"):
            self.instance.chat("second", "voice")
        self.assertEqual(len(self.memory.recent(20)), 2)

    def test_invalid_modality_does_not_write(self):
        with self.assertRaises(ValueError):
            self.instance.chat("hello", "other")
        self.assertEqual(self.memory.recent(20), [])

    def test_parallel_chat_requests_are_serialized(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            turns = list(pool.map(
                lambda i: self.instance.chat(str(i), "voice" if i % 2 else "text"),
                range(8),
            ))
        self.assertEqual(len({t["continuity"]["identity_id"] for t in turns}), 1)
        events = self.memory.recent(20)
        self.assertEqual(len(events), 16)
        self.assertEqual([x["role"] for x in events],
                         ["user", "assistant"] * 8)

    def test_locked_local_route_does_not_fallback_online(self):
        real = Selma0LLMRouterAndroidV1()
        real.local_base = "http://127.0.0.1:8080/v1"
        real.local_model = "stable-local"
        real.online_base = "https://unused.invalid/v1"
        real.online_model = "other"
        with patch.object(real, "_chat", side_effect=[
            OSError("offline"), "should-never-be-called"
        ]) as invoked:
            result = real.reply([{"role": "user", "content": "x"}],
                                locked_route="offline-local")
        self.assertEqual(result["route"], "unavailable")
        self.assertEqual(invoked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
