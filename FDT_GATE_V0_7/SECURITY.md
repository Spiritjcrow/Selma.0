# Security invariants — WingDingynouse HARDSTONE v0.7

1. **Intent is never authority.** Agent/model text and payload fields are untrusted data.
2. **Default deny.** No rule or no valid capability means no host effect.
3. **Genesis root.** Root capability grants and policy signing terminate at explicitly trusted Genesis keys.
4. **Delegation narrows only.** Child scope/effects/methods/time may not exceed the parent grant.
5. **Revocation wins immediately.** A revoked grant or approval is invalid on the next authorization.
6. **Approval binds the exact action hash.** It cannot authorize a changed resource, payload, method, or actor.
7. **One-time approvals are consumed before execution.** Reuse is rejected.
8. **Principal identity is out-of-band at the HTTP boundary.** Bearer token maps to principal; request actor cannot override it.
9. **Adapters are explicit.** An allowed decision with no registered adapter still cannot execute a host effect.
10. **Filesystem paths are confined.** Resolved paths must remain inside the configured root.
11. **HTTP is HTTPS + host allowlist with redirects disabled.** DNS/IP controls should still be strengthened for hostile enterprise deployments.
12. **Evidence is tamper-evident, not magically immutable.** Protect the audit file/storage permissions and export/seal it externally when needed.
13. **Canonical Key Grammar is not cryptographic authorization.** It is parser/language identity only.

## Production hardening still required

- external KMS/HSM/TPM/StrongBox custody and key rotation;
- mature workload identity (OIDC/OAuth/mTLS) instead of static bearer tokens;
- process isolation/sandboxing around adapters;
- hardened DNS/IP controls for HTTP to reduce SSRF/rebinding risk;
- third-party cryptographic/security review;
- high-volume fuzzing, mutation testing, and formal property suites;
- signed binary/package supply chain and reproducible release pipeline;
- multi-tenant isolation, administrator/reviewer separation, and incident kill path.
