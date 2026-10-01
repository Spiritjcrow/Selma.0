from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
import zlib

from core.avatar_runtime import (
    AvatarChunkError,
    AvatarEvent,
    AvatarPackSignatureError,
    AvatarRuntime,
    BoundedChunkReader,
    ByteBufferPool,
    GazeTarget,
    PerformanceController,
    RuntimeMetrics,
    SoftwareAvatarRenderer,
    load_verified_manifest,
)
from core.protocols import AvatarState, CancellationToken


def manifest_bytes(stored: bytes, *, raw: bytes | None = None, compression: str = "none") -> bytes:
    raw = stored if raw is None else raw
    return json.dumps({
        "schema_version": 1,
        "pack_id": "selma.baseline",
        "pack_version": "1.0.0",
        "identity_id": "selma.adult.baseline",
        "minimum_runtime_version": "1.0.0",
        "capabilities": ["face", "gaze", "viseme", "gesture"],
        "chunks": [{
            "chunk_id": "face-neutral",
            "path": "chunks/face.bin",
            "sha256": sha256(stored).hexdigest(),
            "stored_size": len(stored),
            "raw_size": len(raw),
            "compression": compression,
        }],
    }).encode()


class AvatarPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "chunks").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def load(self, stored: bytes, *, raw: bytes | None = None, compression: str = "none"):
        (self.root / "chunks/face.bin").write_bytes(stored)
        (self.root / "manifest.json").write_bytes(manifest_bytes(stored, raw=raw, compression=compression))
        (self.root / "manifest.sig").write_bytes(b"ok")
        return load_verified_manifest(
            self.root / "manifest.json",
            self.root / "manifest.sig",
            lambda payload, sig: sig == b"ok" and b"selma.baseline" in payload,
        )

    def test_signature_verification_is_required(self) -> None:
        stored = b"portrait"
        (self.root / "manifest.json").write_bytes(manifest_bytes(stored))
        (self.root / "manifest.sig").write_bytes(b"bad")
        with self.assertRaises(AvatarPackSignatureError):
            load_verified_manifest(
                self.root / "manifest.json",
                self.root / "manifest.sig",
                lambda *_: False,
            )

    def test_newer_runtime_requirement_fails_closed(self) -> None:
        data = json.loads(manifest_bytes(b"portrait"))
        data["minimum_runtime_version"] = "99.0.0"
        (self.root / "manifest.json").write_text(json.dumps(data))
        (self.root / "manifest.sig").write_bytes(b"ok")
        with self.assertRaisesRegex(Exception, "newer runtime"):
            load_verified_manifest(
                self.root / "manifest.json",
                self.root / "manifest.sig",
                lambda *_: True,
            )

    def test_corrupt_chunk_fails_closed(self) -> None:
        manifest = self.load(b"portrait")
        (self.root / "chunks/face.bin").write_bytes(b"tampered")
        with self.assertRaises(AvatarChunkError):
            BoundedChunkReader(self.root, manifest).read("face-neutral")

    def test_decompression_limit_rejects_declared_bomb(self) -> None:
        raw = b"A" * 4096
        stored = zlib.compress(raw)
        manifest = self.load(stored, raw=raw, compression="zlib")
        with self.assertRaises(AvatarChunkError):
            BoundedChunkReader(self.root, manifest, max_raw_chunk_bytes=1024).read("face-neutral")

    def test_cache_is_bounded(self) -> None:
        manifest = self.load(b"portrait")
        reader = BoundedChunkReader(self.root, manifest, cache_ceiling_bytes=4)
        self.assertEqual(b"portrait", reader.read("face-neutral"))
        self.assertEqual(0, reader.cache_bytes)

    def test_cancelled_chunk_read_fails_before_io(self) -> None:
        manifest = self.load(b"portrait")
        token = CancellationToken()
        token.cancel()
        with self.assertRaisesRegex(AvatarChunkError, "cancelled"):
            BoundedChunkReader(self.root, manifest).read("face-neutral", cancellation=token)


class RuntimeTests(unittest.TestCase):
    def test_stale_sequence_and_generation_are_ignored(self) -> None:
        runtime = AvatarRuntime()
        generation = runtime.generation
        event = AvatarEvent(1, generation, AvatarState.LISTENING, gaze=GazeTarget(.2, -.1))
        self.assertIsNotNone(runtime.apply(event))
        self.assertIsNone(runtime.apply(event))
        runtime.next_generation()
        self.assertIsNone(runtime.apply(AvatarEvent(2, generation, AvatarState.THINKING)))

    def test_user_interrupt_drains_audio(self) -> None:
        calls = []
        runtime = AvatarRuntime(audio_drain=lambda: calls.append("drain"))
        runtime.apply(AvatarEvent(0, runtime.generation, AvatarState.INTERRUPTED, user_priority=True))
        self.assertEqual(["drain"], calls)

    def test_software_renderer_is_deterministic_and_no_zero_copy(self) -> None:
        runtime = AvatarRuntime(SoftwareAvatarRenderer())
        event = AvatarEvent(
            0, 0, AvatarState.SPEAKING,
            expression="warm", viseme="aa", mouth_open=.6,
        )
        snapshot = runtime.apply(event)
        self.assertEqual(1, snapshot.frame_number)
        self.assertEqual("aa", snapshot.viseme)
        self.assertFalse(runtime.request_zero_copy())

    def test_buffer_pool_reuses_and_zeroizes(self) -> None:
        pool = ByteBufferPool(buffer_size=8, capacity=1)
        buffer = pool.acquire()
        buffer[:] = b"12345678"
        pool.release(buffer)
        again = pool.acquire()
        self.assertIs(buffer, again)
        self.assertEqual(bytearray(8), again)

    def test_kill_switch_stops_audio_capture_and_rendering(self) -> None:
        calls = []
        runtime = AvatarRuntime(
            audio_drain=lambda: calls.append("audio"),
            capture_stop=lambda: calls.append("capture"),
        )
        runtime.apply(AvatarEvent(0, 0, AvatarState.IDLE))
        runtime.kill()
        self.assertTrue(runtime.killed)
        self.assertEqual(["audio", "capture"], calls)
        self.assertIsNone(runtime.snapshot)
        self.assertIsNone(runtime.apply(AvatarEvent(1, 0, AvatarState.SPEAKING)))
        with self.assertRaisesRegex(RuntimeError, "killed"):
            runtime.next_generation()

    def test_cancelled_event_is_ignored(self) -> None:
        token = CancellationToken()
        token.cancel()
        runtime = AvatarRuntime()
        self.assertIsNone(
            runtime.apply(AvatarEvent(0, 0, AvatarState.IDLE), cancellation=token)
        )


class PerformanceTests(unittest.TestCase):
    def test_no_telemetry_means_no_inference_or_degradation(self) -> None:
        controller = PerformanceController()
        before = controller.budget
        self.assertEqual(before, controller.observe(RuntimeMetrics()))

    def test_explicit_pressure_degrades_conservatively(self) -> None:
        controller = PerformanceController()
        after = controller.observe(
            RuntimeMetrics(
                frame_time_ms=60,
                memory_pressure=.9,
                thermal_level=3,
                battery_saver=True,
            )
        )
        self.assertLess(after.target_fps, 30)
        self.assertLess(after.resolution_scale, 1.0)
        self.assertFalse(after.effects_enabled)
        self.assertLess(after.cache_ceiling_bytes, 8 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
