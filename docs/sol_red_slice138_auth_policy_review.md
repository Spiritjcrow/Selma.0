# Sol Red Slice 138: loopback approval contract (draft)

Base: `main` at `f19a514846e7dcd26c90b461d7107d73dc8fc163`. This review branch is non-deployable and must not be merged without independent QA.

## Contract

- Distinguish local clients by independently provisioned high-entropy credentials; store only digests in the policy.
- Require trusted native/OS user-presence evidence before minting an approval. No HTTP endpoint or JSON boolean may mint one.
- Bind short-lived, single-use HMAC approval evidence to client identity, exact tool, canonical arguments SHA-256 and request ID.
- Authenticate all private GET and POST routes, leaving only a minimal health endpoint public.
- Enforce exact browser Origin (scheme, host, port) on mutations, alongside client authentication; default loopback-only.
- Never log tokens, approval evidence, sensitive arguments or raw exception details.

## Integration gates (not implemented by this contract)

Android/Termux secure credential provisioning, trusted user-presence adapter, persistent replay invalidation across restart, browser UI pairing flow and real Android smoke tests. Existing UI must continue to function after pairing. Until those gates pass, the policy is not wired into production handlers and issue #43 remains OPEN.

Only owned disposable fixtures and static tests may be used; no live endpoint probes, SMS, secrets, merges or deployments.
