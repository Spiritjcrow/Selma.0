# Avatar Pack Ed25519 trust boundary

Production Avatar Packs use detached Ed25519 signatures over the canonical unsigned manifest. The verifier accepts only exact `Ed25519`, a 64-byte signature, and a 32-byte public key whose stable ID is marked `trusted` in the local registry. Unknown or revoked keys fail closed.

The registry contains public keys only. Private signing keys must never enter the repository, application package, logs, backups, or runtime trust store. Pack signing belongs in a separately controlled release process. Key rotation adds a new public key before packs use it; revocation changes the old key to `revoked` while retaining its ID for audit history.

`cryptography` is the vetted implementation boundary. If the dependency or backend is unavailable, verification returns false; Selma does not try a weaker algorithm, invoke a shell command, fetch keys from a network, or silently trust the pack. Dependency versions are constrained in `requirements/avatar-ed25519.txt` and remain subject to the normal security-update process.

Tests use the public RFC 8032 test-vector seed solely to generate deterministic signatures. It is globally published test material and is never a production signing key.

Run `python3 -m unittest tests.test_avatar_ed25519 -v`. The tests cover valid/tampered payloads, unknown and revoked keys, algorithm confusion, private-field rejection, duplicate IDs, malformed key length, bounded reads, strict UTF-8, and end-to-end `AvatarPack.open()` verification.

Primary specifications: [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032) and the [`cryptography` Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
