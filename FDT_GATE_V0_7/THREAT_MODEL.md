# Threat model — FDT Gate v0.7

## Protected assets
Genesis identity and keys; signed policy; capability grants; approvals; revocation state; runtime signer;
protected host resources; decision/effect provenance; audit evidence.

## Addressed in this reference runtime
- prompt injection attempting to self-grant authority;
- ambient/self-granted agent permissions;
- scope broadening beyond a signed grant;
- use after expiry or revocation;
- approval reuse for a different action;
- local API actor spoofing when bearer principal mapping is enabled;
- filesystem path traversal beyond configured root;
- silent policy mutation through build-ID and signature verification;
- audit-record alteration through hash-chain verification;
- unregistered effects reaching host execution.

## Not claimed solved
- compromised OS, kernel, hypervisor, Python runtime, or hardware;
- stolen/unlocked private keys;
- malicious cryptographic library;
- all side channels;
- every SSRF/DNS-rebinding edge case in the reference HTTP adapter;
- semantic vulnerabilities in future third-party adapters;
- social engineering of an authorized approver;
- production-grade identity lifecycle, key custody, or multi-tenancy.
