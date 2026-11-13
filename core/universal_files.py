"""Selma Universal Files v0.1: offline, sandboxed local storage provider.

Provider interface allows future SAF (Android), desktop and cloud backends.
This prototype is intended for trusted, user-owned directories, not hostile
multi-user filesystems with concurrent symlink/directory replacement.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Protocol


class FileBoundaryError(ValueError):
    """A path or operation was disallowed by the storage boundary."""


class FileProvider(Protocol):
    def list_dir(self, folder: str = "") -> dict: ...
    def copy_file(self, source: str, target_folder: str) -> dict: ...
    def move_file(self, source: str, target_folder: str) -> dict: ...
    def mkdir(self, parent: str, name: str) -> dict: ...


class LocalFileProvider:
    """Directory-scoped provider; paths in the API always use '/' separators."""

    MAX_ENTRIES = 1500

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise FileBoundaryError("root must be a directory")

    def _path(self, value: str, *, directory: bool | None = None) -> Path:
        if not isinstance(value, str) or '\\' in value or '\x00' in value:
            raise FileBoundaryError("invalid virtual path")
        if value.startswith('/') or any(part in ('..', '.') for part in value.split('/')):
            raise FileBoundaryError("absolute and parent paths are not allowed")
        logical = PurePosixPath(value)
        candidate = self.root.joinpath(*logical.parts)
        # Refuse symlinks at every step instead of allowing traversal out of root.
        current = self.root
        for part in logical.parts:
            current = current / part
            if current.is_symlink():
                raise FileBoundaryError("symbolic links are not accessible")
        try:
            candidate.resolve(strict=False).relative_to(self.root)
        except ValueError as exc:
            raise FileBoundaryError("path escapes selected root") from exc
        if not candidate.exists():
            raise FileNotFoundError("item not found")
        if directory is True and not candidate.is_dir():
            raise FileBoundaryError("expected a directory")
        if directory is False and not candidate.is_file():
            raise FileBoundaryError("only regular files can be transferred")
        return candidate

    def _rel(self, path: Path) -> str:
        return '' if path == self.root else path.relative_to(self.root).as_posix()

    def list_dir(self, folder: str = "") -> dict:
        parent = self._path(folder, directory=True)
        entries = []
        truncated = False
        for child in sorted(parent.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
            if len(entries) >= self.MAX_ENTRIES:
                truncated = True
                break
            symlink = child.is_symlink()
            kind = "link" if symlink else "folder" if child.is_dir() else "file"
            entries.append({"name": child.name, "path": self._rel(child), "type": kind})
        return {"path": self._rel(parent), "entries": entries, "truncated": truncated}

    def _destination(self, source: str, target_folder: str) -> tuple[Path, Path]:
        src = self._path(source, directory=False)
        folder = self._path(target_folder, directory=True)
        dest = folder / src.name
        if dest.exists() or dest.is_symlink():
            raise FileExistsError("destination already exists; overwriting is disabled")
        return src, dest

    def copy_file(self, source: str, target_folder: str) -> dict:
        src, dest = self._destination(source, target_folder)
        # Exclusive create refuses overwrites even if the file appears after check.
        created = False
        try:
            with src.open('rb') as incoming:
                with dest.open('xb') as outgoing:
                    created = True
                    shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
        except Exception:
            if created:
                dest.unlink(missing_ok=True)
            raise
        return {"path": self._rel(dest)}

    def move_file(self, source: str, target_folder: str) -> dict:
        src, dest = self._destination(source, target_folder)
        # os.link gives an atomic no-overwrite destination on one filesystem.
        # Cross-filesystem moves fail closed rather than risking partial data loss.
        os.link(src, dest, follow_symlinks=False)
        try:
            src.unlink()
        except OSError:
            dest.unlink()
            raise
        return {"path": self._rel(dest)}

    def mkdir(self, parent: str, name: str) -> dict:
        directory = self._path(parent, directory=True)
        if (not isinstance(name, str) or not name or name in ('.', '..') or
                '/' in name or '\\' in name or '\x00' in name):
            raise FileBoundaryError("invalid folder name")
        target = directory / name
        target.mkdir(exist_ok=False)
        return {"path": self._rel(target)}
