"""Durable single-logical-instance continuity for Selma.0.

Text and voice are input modalities for one conversational identity. Switching
modality must never create a new identity, reset context, or change the pinned
language-model provider. Explicit owner-approved context refresh is separate.
"""

import hashlib
import json
import threading
import time
import uuid

VALID_MODALITIES = frozenset({"text", "voice"})


def validate_modality(modality):
    if not isinstance(modality, str) or modality not in VALID_MODALITIES:
        raise ValueError("modality must be 'text' or 'voice'")
    return modality


def provider_fingerprint(route, base_url, model_name):
    if route not in ("offline-local", "online-fallback"):
        raise ValueError("cannot pin an unavailable provider")
    document = json.dumps(
        [route, str(base_url).rstrip("/"), str(model_name)],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


class Selma0ContinuityAndroidV1:
    """A durable identity record in the existing SQLite memory database."""

    def __init__(self, memory):
        self.memory = memory
        self._lock = getattr(memory, "_lock", threading.RLock())
        with self._lock:
            self.memory.conn.execute(
                """CREATE TABLE IF NOT EXISTS selma0_instance_v1 (
                    slot TEXT PRIMARY KEY,
                    identity_id TEXT NOT NULL,
                    thread_id TEXT,
                    context_generation INTEGER NOT NULL,
                    locked_route TEXT,
                    provider_fingerprint TEXT,
                    updated_at REAL NOT NULL
                )"""
            )
            # Upgrade a prototype database without changing its established identity.
            columns = {
                row[1] for row in self.memory.conn.execute(
                    "PRAGMA table_info(selma0_instance_v1)"
                ).fetchall()
            }
            if "thread_id" not in columns:
                self.memory.conn.execute(
                    "ALTER TABLE selma0_instance_v1 ADD COLUMN thread_id TEXT"
                )
            self.memory.conn.execute(
                """INSERT OR IGNORE INTO selma0_instance_v1
                   (slot, identity_id, thread_id, context_generation, locked_route,
                    provider_fingerprint, updated_at)
                   VALUES ('primary', ?, ?, 0, NULL, NULL, ?)""",
                (uuid.uuid4().hex, uuid.uuid4().hex, time.time()),
            )
            self.memory.conn.execute(
                """UPDATE selma0_instance_v1 SET thread_id=?
                   WHERE slot='primary' AND thread_id IS NULL""",
                (uuid.uuid4().hex,),
            )
            self.memory.conn.commit()

    def current(self):
        with self._lock:
            row = self.memory.conn.execute(
                """SELECT identity_id, thread_id, context_generation,
                          locked_route, provider_fingerprint
                   FROM selma0_instance_v1 WHERE slot='primary'"""
            ).fetchone()
            if row is None:
                raise RuntimeError("Selma instance identity is unavailable")
            return {
                "identity_id": row[0],
                "thread_id": row[1],
                "context_generation": row[2],
                "locked_route": row[3],
                "provider_fingerprint": row[4],
            }

    def pin_provider(self, route, fingerprint):
        if route not in ("offline-local", "online-fallback"):
            raise ValueError("only successful providers may be pinned")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("provider fingerprint is invalid")
        with self._lock:
            state = self.current()
            if state["locked_route"] is not None:
                if (state["locked_route"], state["provider_fingerprint"]) != (
                    route, fingerprint
                ):
                    raise RuntimeError("provider identity changed within active context")
                return self.current()
            self.memory.conn.execute(
                """UPDATE selma0_instance_v1
                   SET locked_route=?, provider_fingerprint=?, updated_at=?
                   WHERE slot='primary' AND locked_route IS NULL""",
                (route, fingerprint, time.time()),
            )
            self.memory.conn.commit()
            return self.current()

    def assert_provider(self, router):
        """Fail before network/model invocation if an existing lock changed."""
        state = self.current()
        route = state["locked_route"]
        if route is not None:
            actual = router.provider_fingerprint(route)
            if actual != state["provider_fingerprint"]:
                raise RuntimeError("configured model changed; explicit context refresh required")
        return state

    def refresh_context(self):
        """Explicit action only; retain identity and complete event archive."""
        with self._lock:
            self.memory.conn.execute(
                """UPDATE selma0_instance_v1
                   SET context_generation=context_generation+1,
                       locked_route=NULL, provider_fingerprint=NULL, updated_at=?
                   WHERE slot='primary'""",
                (time.time(),),
            )
            self.memory.conn.commit()
            return self.current()

    def conversation_history(self, max_messages=40):
        """Read one generation across both modalities; never mix prior refreshes."""
        state = self.current()
        events = self.memory.recent(200)
        out = []
        for event in events:
            if event.get("role") not in ("user", "assistant"):
                continue
            metadata = event.get("metadata") or {}
            if not isinstance(metadata, dict):
                continue
            if (
                metadata.get("identity_id") == state["identity_id"]
                and metadata.get("thread_id") == state["thread_id"]
                and metadata.get("context_generation") == state["context_generation"]
            ):
                out.append(event)
            elif (
                state["context_generation"] == 0
                and "identity_id" not in metadata
                and "context_generation" not in metadata
            ):
                # Existing untagged chat events from before the migration.
                out.append(event)
        return out[-max(1, min(int(max_messages), 200)) :]
