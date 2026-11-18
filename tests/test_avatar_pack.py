from __future__ import annotations

import base64, copy, hashlib, json, tempfile, unittest, zlib
from pathlib import Path

from avatar.pack import AvatarPack, AvatarPackError, _canonical_unsigned
from core.protocols import AvatarState


class ExactTestVerifier:
    """Test-only verifier; never accepted as production cryptography."""
    def __init__(self, payload: bytes, signature: bytes = b"test-signature") -> None:
        self.payload, self.signature = payload, signature
    def verify(self, algorithm, key_id, payload, signature):
        return algorithm == "TEST-ONLY" and key_id == "test:key:v1" and payload == self.payload and signature == self.signature


def manifest_for(data: bytes, *, encoding="stored", decoded_size=None):
    manifest = {
        "schema_version": "1.0.0", "contract": "selma.avatar-pack.v1",
        "pack_id": "avatar-pack:selma.synthetic.test", "pack_version": "1.0.0",
        "personification_id": "personification:selma.synthetic.baseline",
        "states": [state.value for state in AvatarState],
        "chunks": [{"chunk_id": "idle", "path": "chunks/idle.bin", "encoding": encoding,
                    "encoded_size": len(data), "decoded_size": len(data) if decoded_size is None else decoded_size,
                    "sha256": hashlib.sha256(data).hexdigest()}],
        "signature": {"algorithm": "TEST-ONLY", "key_id": "test:key:v1", "value_base64": base64.b64encode(b"test-signature").decode()},
    }
    return manifest


class AvatarPackTests(unittest.TestCase):
    def make_pack(self, root: Path, data=b"idle", **kwargs):
        manifest = manifest_for(data, **kwargs)
        (root / "chunks").mkdir(); (root / "chunks/idle.bin").write_bytes(data)
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def open(self, root, manifest, **kwargs):
        return AvatarPack.open(root, signature_verifier=ExactTestVerifier(_canonical_unsigned(manifest)), **kwargs)

    def test_verified_chunk_reads_and_cache_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=self.make_pack(root, b"abcd")
            pack=self.open(root, manifest, cache_limit_bytes=4)
            self.assertEqual(b"abcd", pack.read_chunk("idle")); self.assertEqual(4, pack.cache_bytes)
            pack.close(); self.assertEqual(0, pack.cache_bytes)

    def test_default_signature_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.make_pack(root)
            with self.assertRaisesRegex(AvatarPackError, "signature verification failed"): AvatarPack.open(root)

    def test_tampered_manifest_fails_signature(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=self.make_pack(root); verifier=ExactTestVerifier(_canonical_unsigned(manifest))
            manifest["pack_version"]="1.0.1"; (root/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AvatarPackError, "signature verification failed"): AvatarPack.open(root, signature_verifier=verifier)

    def test_tampered_chunk_fails_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=self.make_pack(root); (root/"chunks/idle.bin").write_bytes(b"evil")
            with self.assertRaisesRegex(AvatarPackError, "digest mismatch"): self.open(root, manifest).read_chunk("idle")

    def test_path_traversal_and_duplicate_keys_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=self.make_pack(root); manifest["chunks"][0]["path"]="../escape"
            (root/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AvatarPackError, "normalized relative"): self.open(root, manifest)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"manifest.json").write_text('{"schema_version":"1.0.0","schema_version":"1.0.0"}')
            with self.assertRaisesRegex(AvatarPackError, "duplicate manifest key"): AvatarPack.open(root)

    def test_declared_decompression_limit_fails_before_decode(self):
        encoded=zlib.compress(b"A"*1024)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=self.make_pack(root, encoded, encoding="zlib", decoded_size=1024)
            with self.assertRaisesRegex(AvatarPackError, "configured size limit"): self.open(root, manifest, chunk_limit_bytes=128)

    def test_decompression_bomb_cannot_lie_about_decoded_size(self):
        encoded=zlib.compress(b"A"*4096)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=self.make_pack(root, encoded, encoding="zlib", decoded_size=16)
            with self.assertRaisesRegex(AvatarPackError, "limit exceeded"): self.open(root, manifest, chunk_limit_bytes=128).read_chunk("idle")

    def test_gate1_state_contract_is_exact(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=self.make_pack(root); manifest["states"].remove("ERROR")
            (root/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AvatarPackError, "AvatarState contract"): self.open(root, manifest)

if __name__ == "__main__": unittest.main()
