# Avatar Pack v1: verification slice

This first issue #16 slice treats an avatar “ROM” as local, read-only data—not firmware. A pack cannot execute code, request permissions, authorize tools, or modify protected device storage.

## Activation sequence

1. Read a size-bounded UTF-8 JSON manifest and reject duplicate keys.
2. Verify schema/contract versions, stable IDs, and exact Gate 1 avatar states.
3. Canonicalize the unsigned manifest and verify its detached signature through a platform cryptography adapter.
4. Validate unique chunk IDs, normalized relative paths, hashes, encodings, and encoded/decoded size ceilings.
5. Lazily read only requested chunks, verify their encoded SHA-256 before decoding, and retain decoded bytes only inside a byte-bounded LRU cache.
6. On any error, refuse activation and retain the last known-good pack.

`AvatarPack.open()` uses a reject-all signature policy unless a verifier is supplied. `TEST-ONLY` in unit tests is deliberately not cryptography and must never ship as a production verifier. The production adapter should accept only the approved Ed25519 algorithm and a locally trusted key ID.

This slice contains no image, voice, biometric, executable, third-party, or model asset. Later pack-building work must connect every asset to Personification Registry provenance, consent, license, attribution, and commercial-use records.

## Resource limits

The runtime bounds manifest size, chunk count, encoded size, decoded size and total decoded cache bytes. Paths cannot be absolute or contain `.`/`..`. Zero-copy and memory mapping are later platform optimizations; neither is assumed here.

## Verification

Run `python3 -m unittest tests.test_avatar_pack -v`. Tests cover valid lazy reading, cache clearing, unsigned rejection, manifest and chunk tampering, traversal, duplicate JSON keys, decompression ceilings, and Gate 1 state compatibility.

Standards used: [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core), [RFC 8032 Ed25519](https://www.rfc-editor.org/rfc/rfc8032), and [FIPS 180-4 SHA-256](https://csrc.nist.gov/pubs/fips/180-4/upd1/final).
