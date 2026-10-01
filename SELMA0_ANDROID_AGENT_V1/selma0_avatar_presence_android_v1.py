#!/usr/bin/env python3
"""Verified local Adult Mode presence adapter for the Android/Termux runtime."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import Any
import zipfile

from core.avatar_runtime import (
    AvatarEvent,
    AvatarPackError,
    AvatarRuntime,
    AvatarState,
    BoundedChunkReader,
    GazeTarget,
    load_verified_manifest,
)

SELMA0_BASE_V1 = Path(os.path.expanduser(os.getenv("SELMA0_BASE_V1", "~/SELMA0_ANDROID_AGENT_V1")))
SELMA0_DATA_V1 = SELMA0_BASE_V1 / "selma0_data_android_v1"
SELMA0_AVATAR_DIR_V1 = Path(
    os.path.expanduser(
        os.getenv("SELMA0_AVATAR_PACK_DIR_V1", str(SELMA0_BASE_V1 / "selma0_avatar_pack_v1"))
    )
)
SELMA0_AVATAR_TRUST_KEY_V1 = Path(
    os.path.expanduser(
        os.getenv(
            "SELMA0_AVATAR_TRUSTED_PUBLIC_KEY_V1",
            str(SELMA0_DATA_V1 / "selma0_avatar_trusted_public_v1.pem"),
        )
    )
)

_MAX_ARCHIVE_FILES = 128
_MAX_ARCHIVE_FILE_BYTES = 16 * 1024 * 1024
_MAX_ARCHIVE_TOTAL_BYTES = 64 * 1024 * 1024


def _load_public_key(path: Path):
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError as exc:
        raise RuntimeError(
            "python-cryptography is required for signed avatar-pack verification"
        ) from exc
    return load_pem_public_key(path.read_bytes())


def _verifier(public_key):
    def verify(payload: bytes, signature: bytes) -> bool:
        try:
            public_key.verify(signature, payload)
            return True
        except Exception:
            return False

    return verify


def _safe_extract(zip_path: Path, destination: Path) -> None:
    total = 0
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        if len(infos) > _MAX_ARCHIVE_FILES:
            raise AvatarPackError("avatar pack contains too many files")
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or info.filename in {"", "."}:
                raise AvatarPackError("avatar pack contains an unsafe path")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and stat.S_ISLNK(unix_mode):
                raise AvatarPackError("avatar pack may not contain symlinks")
            if info.file_size > _MAX_ARCHIVE_FILE_BYTES:
                raise AvatarPackError("avatar pack file exceeds size ceiling")
            total += info.file_size
            if total > _MAX_ARCHIVE_TOTAL_BYTES:
                raise AvatarPackError("avatar pack exceeds total size ceiling")
        archive.extractall(destination)


class Selma0AvatarPresenceAndroidV1:
    def __init__(
        self,
        *,
        pack_dir: Path = SELMA0_AVATAR_DIR_V1,
        trust_key: Path = SELMA0_AVATAR_TRUST_KEY_V1,
    ) -> None:
        self.pack_dir = Path(pack_dir)
        self.trust_key = Path(trust_key)
        self._manifest = None
        self._reader: BoundedChunkReader | None = None
        self._runtime: AvatarRuntime | None = None
        self._state_map: dict[str, dict[str, Any]] = {}
        self._sequence = 0
        self._error: str | None = None
        self.boot()

    @property
    def loaded(self) -> bool:
        return self._manifest is not None and self._reader is not None and self._runtime is not None

    def _activate(self, pack_dir: Path, trust_key: Path) -> None:
        public_key = _load_public_key(trust_key)
        manifest = load_verified_manifest(
            pack_dir / "manifest.json",
            pack_dir / "manifest.sig",
            _verifier(public_key),
        )
        reader = BoundedChunkReader(
            pack_dir,
            manifest,
            cache_ceiling_bytes=4 * 1024 * 1024,
            max_stored_chunk_bytes=_MAX_ARCHIVE_FILE_BYTES,
            max_raw_chunk_bytes=_MAX_ARCHIVE_FILE_BYTES,
        )
        for chunk in manifest.chunks:
            reader.read(chunk.chunk_id)
        state_map: dict[str, dict[str, Any]] = {}
        try:
            decoded = json.loads(reader.read("state-map").decode("utf-8"))
            if isinstance(decoded, dict):
                for key, value in decoded.items():
                    if isinstance(key, str) and isinstance(value, dict):
                        state_map[key] = value
        except KeyError:
            pass
        except Exception as exc:
            raise AvatarPackError(f"invalid avatar state map: {exc}") from exc
        runtime = AvatarRuntime(chunk_reader=reader)
        self.pack_dir = pack_dir
        self._manifest = manifest
        self._reader = reader
        self._runtime = runtime
        self._state_map = state_map
        self._sequence = 0
        self._error = None
        self.transition(AvatarState.IDLE)

    def boot(self) -> dict[str, Any]:
        self._manifest = None
        self._reader = None
        self._runtime = None
        self._state_map = {}
        self._error = None
        if not self.pack_dir.is_dir():
            self._error = f"avatar pack not installed at {self.pack_dir}"
            return self.status()
        if not self.trust_key.is_file():
            self._error = f"trusted avatar public key is not pinned at {self.trust_key}"
            return self.status()
        try:
            self._activate(self.pack_dir, self.trust_key)
        except Exception as exc:
            self._error = str(exc)
        return self.status()

    def install_zip(self, source: str, *, trust_on_first_use: bool = False) -> dict[str, Any]:
        zip_path = Path(os.path.expanduser(source)).resolve()
        if not zip_path.is_file():
            raise ValueError(f"avatar pack archive not found: {zip_path}")
        SELMA0_DATA_V1.mkdir(parents=True, exist_ok=True)
        self.pack_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="selma-avatar-") as temp:
            staging = Path(temp) / "pack"
            staging.mkdir()
            _safe_extract(zip_path, staging)
            bundled_key = staging / "public_key.pem"
            if self.trust_key.is_file():
                key_to_use = self.trust_key
            else:
                if not trust_on_first_use:
                    raise PermissionError(
                        "no trusted avatar key is pinned; explicit trust_on_first_use is required"
                    )
                if not bundled_key.is_file():
                    raise AvatarPackError("avatar pack has no public_key.pem for first-use trust")
                key_to_use = bundled_key
            self._activate(staging, key_to_use)
            if not self.trust_key.is_file():
                self.trust_key.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundled_key, self.trust_key)
            rollback = self.pack_dir.with_name(self.pack_dir.name + ".rollback")
            if rollback.exists():
                shutil.rmtree(rollback)
            if self.pack_dir.exists():
                self.pack_dir.rename(rollback)
            shutil.copytree(staging, self.pack_dir)
        self._activate(self.pack_dir, self.trust_key)
        result = self.status()
        result["installed_from"] = str(zip_path)
        result["trusted_public_key_sha256"] = sha256(self.trust_key.read_bytes()).hexdigest()
        return result

    def transition(
        self,
        state: AvatarState,
        *,
        expression: str | None = None,
        gesture: str | None = None,
        gaze_x: float = 0.0,
        gaze_y: float = 0.0,
        user_priority: bool = False,
    ) -> dict[str, Any]:
        if not self.loaded:
            return self.status()
        mapping = self._state_map.get(state.value, {})
        self._sequence += 1
        snapshot = self._runtime.apply(
            AvatarEvent(
                sequence=self._sequence,
                generation=self._runtime.generation,
                state=state,
                expression=expression or str(mapping.get("expression", "neutral")),
                gesture=gesture or str(mapping.get("gesture", "none")),
                gaze=GazeTarget(float(gaze_x), float(gaze_y)),
                user_priority=user_priority,
            )
        )
        return self.status() if snapshot is None else self.status(snapshot=snapshot)

    def update_gaze(self, gaze_x: float, gaze_y: float) -> dict[str, Any]:
        if not self.loaded:
            return self.status()
        snapshot = self._runtime.snapshot
        state = AvatarState.IDLE if snapshot is None else snapshot.state
        return self.transition(
            state,
            expression=None if snapshot is None else snapshot.expression,
            gesture=None if snapshot is None else snapshot.gesture,
            gaze_x=gaze_x,
            gaze_y=gaze_y,
        )

    def current_asset(self) -> tuple[bytes, str, str]:
        if not self.loaded:
            raise RuntimeError(self._error or "avatar pack unavailable")
        snapshot = self._runtime.snapshot
        state = AvatarState.IDLE.value if snapshot is None else snapshot.state.value
        mapping = self._state_map.get(state) or self._state_map.get(AvatarState.IDLE.value) or {}
        chunk_id = str(mapping.get("chunk_id", "idle"))
        if (
            snapshot is not None
            and max(abs(snapshot.gaze.x), abs(snapshot.gaze.y)) >= 0.18
            and any(item.chunk_id == "gaze" for item in self._manifest.chunks)
        ):
            chunk_id = "gaze"
        payload = self._reader.read(chunk_id)
        meta = next((item for item in self._manifest.chunks if item.chunk_id == chunk_id), None)
        filename = Path(meta.path).name if meta else chunk_id
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return payload, mime, chunk_id

    def greet(self) -> dict[str, Any]:
        if not self.loaded:
            return self.status()
        mapping = self._state_map.get("GREETING", {})
        self._sequence += 1
        snapshot = self._runtime.apply(
            AvatarEvent(
                sequence=self._sequence,
                generation=self._runtime.generation,
                state=AvatarState.IDLE,
                expression=str(mapping.get("expression", "warm")),
                gesture=str(mapping.get("gesture", "wave")),
            )
        )
        result = self.status(snapshot=snapshot)
        result["asset_override"] = str(mapping.get("chunk_id", "greeting"))
        return result

    def asset_by_chunk(self, chunk_id: str) -> tuple[bytes, str]:
        if not self.loaded:
            raise RuntimeError(self._error or "avatar pack unavailable")
        payload = self._reader.read(str(chunk_id))
        meta = next((item for item in self._manifest.chunks if item.chunk_id == chunk_id), None)
        filename = Path(meta.path).name if meta else str(chunk_id)
        return payload, mimetypes.guess_type(filename)[0] or "application/octet-stream"

    def kill(self) -> dict[str, Any]:
        if self._runtime is not None:
            self._runtime.kill()
        return self.status()

    def restart(self) -> dict[str, Any]:
        return self.boot()

    def status(self, *, snapshot=None) -> dict[str, Any]:
        if snapshot is None and self._runtime is not None:
            snapshot = self._runtime.snapshot
        return {
            "available": self.loaded and not bool(self._runtime and self._runtime.killed),
            "pack_loaded": self.loaded,
            "verified": self.loaded,
            "pack_id": getattr(self._manifest, "pack_id", None),
            "identity_id": getattr(self._manifest, "identity_id", None),
            "state": None if snapshot is None else snapshot.state.value,
            "expression": None if snapshot is None else snapshot.expression,
            "gesture": None if snapshot is None else snapshot.gesture,
            "sequence": None if snapshot is None else snapshot.sequence,
            "gaze_x": None if snapshot is None else snapshot.gaze.x,
            "gaze_y": None if snapshot is None else snapshot.gaze.y,
            "viseme": None if snapshot is None else snapshot.viseme,
            "mouth_open": None if snapshot is None else snapshot.mouth_open,
            "killed": bool(self._runtime and self._runtime.killed),
            "offline": True,
            "camera_tracking": False,
            "lip_sync": False,
            "renderer": "software/sprite fallback",
            "error": self._error,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Selma Adult Mode local avatar-pack manager")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    install = sub.add_parser("install")
    install.add_argument("archive")
    install.add_argument("--trust-on-first-use", action="store_true")
    args = parser.parse_args()
    presence = Selma0AvatarPresenceAndroidV1()
    if args.command == "install":
        result = presence.install_zip(
            args.archive,
            trust_on_first_use=args.trust_on_first_use,
        )
    else:
        result = presence.status()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
