#!/usr/bin/env python3
"""Build and verify signed Selma avatar data packs.

Private keys are never embedded in a pack. The builder creates a device/local
Ed25519 key only when explicitly requested and writes it with mode 0600.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import Mapping

SCHEMA_VERSION = 1
RUNTIME_VERSION = "1.0.0"


def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise SystemExit("cryptography is required for avatar pack signing/verification") from exc
    return serialization, Ed25519PrivateKey


def _load_json(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _canonical(manifest: Mapping[str, object]) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_key(private_key_path: Path) -> str:
    serialization, Ed25519PrivateKey = _crypto()
    if private_key_path.exists():
        raise FileExistsError(f"refusing to replace existing key: {private_key_path}")
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    os.chmod(private_key_path, 0o600)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return sha256(public).hexdigest()


def build_pack(
    source_dir: Path,
    output_dir: Path,
    asset_map_path: Path,
    private_key_path: Path,
    *,
    pack_id: str,
    identity_id: str,
    pack_version: str = "1.0.0",
) -> dict[str, object]:
    serialization, _ = _crypto()
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    assets = _load_json(asset_map_path)
    if not assets:
        raise ValueError("asset map must not be empty")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True)
    chunks: list[dict[str, object]] = []
    for chunk_id, rel in sorted(assets.items()):
        if not isinstance(chunk_id, str) or not chunk_id.strip() or not isinstance(rel, str):
            raise ValueError("asset map must be {nonempty-string: relative-path}")
        rel_path = PurePosixPath(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts or rel in {"", "."}:
            raise ValueError(f"unsafe asset path: {rel}")
        src = (source_dir / rel).resolve()
        try:
            src.relative_to(source_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"asset escaped source directory: {rel}") from exc
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = chunks_dir / rel_path.name
        if dst.exists():
            raise ValueError(f"asset basename collision: {dst.name}")
        shutil.copy2(src, dst)
        payload = dst.read_bytes()
        chunks.append({
            "chunk_id": chunk_id,
            "path": f"chunks/{dst.name}",
            "sha256": sha256(payload).hexdigest(),
            "stored_size": len(payload),
            "raw_size": len(payload),
            "compression": "none",
        })
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "identity_id": identity_id,
        "minimum_runtime_version": RUNTIME_VERSION,
        "capabilities": [item["chunk_id"] for item in chunks],
        "chunks": chunks,
    }
    payload = _canonical(manifest)
    key = load_pem_private_key(private_key_path.read_bytes(), password=None)
    signature = key.sign(payload)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (output_dir / "manifest.json").write_bytes(payload)
    (output_dir / "manifest.sig").write_bytes(signature)
    (output_dir / "public_key.pem").write_bytes(public)
    return {
        "pack_id": pack_id,
        "identity_id": identity_id,
        "chunks": len(chunks),
        "public_key_sha256": sha256(public).hexdigest(),
    }


def verify_pack(pack_dir: Path, trusted_public_key: Path | None = None) -> dict[str, object]:
    serialization, _ = _crypto()
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    manifest_path = pack_dir / "manifest.json"
    signature_path = pack_dir / "manifest.sig"
    public_path = trusted_public_key or (pack_dir / "public_key.pem")
    payload = manifest_path.read_bytes()
    manifest = json.loads(payload)
    public_bytes = public_path.read_bytes()
    public = load_pem_public_key(public_bytes)
    public.verify(signature_path.read_bytes(), payload)
    root = pack_dir.resolve()
    checked = 0
    for item in manifest.get("chunks", []):
        path = (root / item["path"]).resolve()
        path.relative_to(root)
        data = path.read_bytes()
        if len(data) != item["stored_size"] or sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"chunk verification failed: {item.get('chunk_id')}")
        checked += 1
    return {
        "pack_id": manifest.get("pack_id"),
        "identity_id": manifest.get("identity_id"),
        "chunks_verified": checked,
        "public_key_sha256": sha256(public_bytes).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    key = sub.add_parser("create-key")
    key.add_argument("path", type=Path)
    build = sub.add_parser("build")
    build.add_argument("--source", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--assets", required=True, type=Path)
    build.add_argument("--private-key", required=True, type=Path)
    build.add_argument("--pack-id", required=True)
    build.add_argument("--identity-id", required=True)
    build.add_argument("--pack-version", default="1.0.0")
    verify = sub.add_parser("verify")
    verify.add_argument("pack", type=Path)
    verify.add_argument("--trusted-public-key", type=Path)
    args = parser.parse_args()
    if args.command == "create-key":
        result = {"private_key": str(args.path), "public_key_sha256": create_key(args.path)}
    elif args.command == "build":
        result = build_pack(
            args.source,
            args.output,
            args.assets,
            args.private_key,
            pack_id=args.pack_id,
            identity_id=args.identity_id,
            pack_version=args.pack_version,
        )
    else:
        result = verify_pack(args.pack, args.trusted_public_key)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
