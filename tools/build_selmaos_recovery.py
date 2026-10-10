#!/usr/bin/env python3
"""Package the single-file SelmaOS recovery desktop for offline distribution.

This script intentionally uses only Python's standard library. It never
connects to a network or edits source files. Building does not prove that
a browser can render the UI on a particular device.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sites" / "selmaos"
DIST = ROOT / "dist"
ARTIFACT = DIST / "selmaos-recovery.zip"
MANIFEST = DIST / "selmaos-recovery.zip.sha256"


def build() -> tuple[Path, str]:
    html = SOURCE / "selmaos.html"
    readme = SOURCE / "README.md"
    for file in (html, readme):
        if not file.is_file() or file.stat().st_size == 0:
            raise FileNotFoundError(f"Required source missing: {file.relative_to(ROOT)}")
    DIST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARTIFACT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in (html, readme):
            info = zipfile.ZipInfo(file.name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, file.read_bytes())
    digest = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
    MANIFEST.write_text(f"{digest}  {ARTIFACT.name}\n", encoding="utf-8")
    return ARTIFACT, digest


if __name__ == "__main__":
    archive, sha256 = build()
    print(f"Created {archive.relative_to(ROOT)}")
    print(f"SHA-256 {sha256}")
    print("Static package only; device/browser execution remains unverified.")
