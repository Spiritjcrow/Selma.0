from __future__ import annotations

import base64, hashlib, json, tempfile, unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from avatar.ed25519 import MAX_TRUST_STORE_BYTES, Ed25519Verifier, TrustStoreError, load_trust_store
from avatar.pack import AvatarPack, AvatarPackError, _canonical_unsigned
from core.protocols import AvatarState

# RFC 8032 test vector 1. Public, non-secret test material only.
SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PUBLIC = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
KEY_ID = "ed25519:test:rfc8032-vector-1"


def store(public=PUBLIC, status="trusted"):
    return {"schema_version":"1.0.0", "algorithm":"Ed25519", "keys":[{
        "key_id":KEY_ID, "public_key_base64":base64.b64encode(public).decode(), "status":status
    }]}


class Ed25519VerifierTests(unittest.TestCase):
    def write_store(self, root: Path, document=None):
        path=root/"trusted-keys.json"; path.write_text(json.dumps(document or store()), encoding="utf-8"); return path

    def test_rfc8032_key_verifies_and_tamper_fails(self):
        with tempfile.TemporaryDirectory() as d:
            verifier=Ed25519Verifier.from_file(self.write_store(Path(d)))
            payload=b"Selma Avatar Pack canonical manifest"
            signature=Ed25519PrivateKey.from_private_bytes(SEED).sign(payload)
            self.assertTrue(verifier.verify("Ed25519", KEY_ID, payload, signature))
            self.assertFalse(verifier.verify("Ed25519", KEY_ID, payload+b"!", signature))

    def test_unknown_revoked_and_wrong_algorithm_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); verifier=Ed25519Verifier.from_file(self.write_store(root))
            signature=Ed25519PrivateKey.from_private_bytes(SEED).sign(b"x")
            self.assertFalse(verifier.verify("Ed25519", "ed25519:unknown", b"x", signature))
            self.assertFalse(verifier.verify("ed25519", KEY_ID, b"x", signature))
            self.write_store(root, store(status="revoked"))
            self.assertFalse(Ed25519Verifier.from_file(root/"trusted-keys.json").verify("Ed25519", KEY_ID, b"x", signature))

    def test_private_or_unknown_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); document=store(); document["keys"][0]["private_key_base64"]="forbidden"
            with self.assertRaisesRegex(TrustStoreError, "private fields"):
                load_trust_store(self.write_store(root, document))

    def test_duplicate_ids_and_malformed_key_lengths_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); duplicate=store(); duplicate["keys"].append(dict(duplicate["keys"][0]))
            with self.assertRaisesRegex(TrustStoreError, "duplicate key_id"): load_trust_store(self.write_store(root, duplicate))
            with self.assertRaisesRegex(TrustStoreError, "32 bytes"): load_trust_store(self.write_store(root, store(public=b"short")))

    def test_oversized_or_non_utf8_store_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            oversized = root / "oversized.json"
            oversized.write_bytes(b" " * (MAX_TRUST_STORE_BYTES + 1))
            with self.assertRaisesRegex(TrustStoreError, "size limit"):
                load_trust_store(oversized)
            utf16 = root / "utf16.json"
            utf16.write_bytes(json.dumps(store()).encode("utf-16"))
            with self.assertRaisesRegex(TrustStoreError, "strict UTF-8"):
                load_trust_store(utf16)

    def test_avatar_pack_integration_accepts_valid_signature_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"chunks").mkdir(); data=b'{"pose":"idle"}'
            (root/"chunks/idle.json").write_bytes(data)
            manifest={
                "schema_version":"1.0.0", "contract":"selma.avatar-pack.v1",
                "pack_id":"avatar-pack:selma.synthetic.rfc-test", "pack_version":"1.0.0",
                "personification_id":"personification:selma.synthetic.baseline",
                "states":[state.value for state in AvatarState],
                "chunks":[{"chunk_id":"idle", "path":"chunks/idle.json", "encoding":"stored",
                    "encoded_size":len(data), "decoded_size":len(data), "sha256":hashlib.sha256(data).hexdigest()}],
                "signature":{"algorithm":"Ed25519", "key_id":KEY_ID, "value_base64":""},
            }
            manifest["signature"]["value_base64"]=base64.b64encode(Ed25519PrivateKey.from_private_bytes(SEED).sign(_canonical_unsigned(manifest))).decode()
            (root/"manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            verifier=Ed25519Verifier.from_file(self.write_store(root))
            self.assertEqual(data, AvatarPack.open(root, signature_verifier=verifier).read_chunk("idle"))
            manifest["pack_version"]="1.0.1"; (root/"manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AvatarPackError, "signature verification failed"):
                AvatarPack.open(root, signature_verifier=verifier)

if __name__ == "__main__": unittest.main()
