# HyperCore 25-point evidence preflight | implementation/handoff

**Scope:** Existing draft PR #114, offline-only Selma° HyperCore web prototype. These are 25 **evidence-field checkpoints**, not HTTP routes, active schedulers, signed attestations or 25 independent verified build results.

## Implementation map

| ID | Ledger field | Check |
|---|---|---|
| 01 | source | Immutable 40-character Git commit SHA |
| 02 | source | HTTPS commit permalink |
| 03 | source | Repository owner/name |
| 04 | source | Branch or ref label |
| 05 | runner | Job/build identifier |
| 06 | runner | Codemagic build detail link |
| 07 | runner | Workflow identity |
| 08 | runner | Machine/runner profile |
| 09 | sdk | Java 17 reference |
| 10 | sdk | Android SDK 35 reference |
| 11 | sdk | Build-tools 35.0.0 reference |
| 12 | sdk | Gradle 8.9 reference |
| 13 | lint | Lint task invocation |
| 14 | lint | Explicit lint outcome (can be FAIL) |
| 15 | lint | Lint report filename |
| 16 | tests | Unit-test task invocation |
| 17 | tests | Test count or summary |
| 18 | tests | Test report reference |
| 19 | apk | APK filename |
| 20 | apk | Artifact HTTPS link |
| 21 | apk | Artifact size in bytes |
| 22 | sha256 | 64-hex SHA-256 |
| 23 | sha256 | Hashing command evidence |
| 24 | install | Device/model reference |
| 25 | install | Install/smoke-test observation (can be FAIL) |

**What is implemented:** one explicit structural regex per checkpoint, read-only mapping from 8 existing local evidence fields, deterministic RECORDED_PATTERN / MISSING / REVIEW_FORMAT classification, numerical summary, keyboard-focus next action, import of schema-v1 JSON (100 KB max), non-mutating localStorage read, summary-only export without raw evidence, responsive semantic page, and tests. No new background process or API permission surface.

**Truth boundary:** The word RECORDED_PATTERN means that some supplied text matched a pattern. It never means CI succeeded, a file is genuine, a checksum matches the APK, a phone installed software, or an actor is authenticated. Even a recorded **FAIL** remains a recorded field. Machine-verified count stays zero. An entered digest is not computed from the APK. Never use this tool as a production approval gate.

## Evidence for this source slice
- `node --check assets/preflight.js`: PASS in local authoring runtime.
- `node --test tests/preflight.test.cjs`: **36/36 PASS** in local Node 22; one fixture for each of 25 patterns, plus schema/safety/collision and integrity invariants.
- Local Git blob hashes matched the three connector readbacks on draft PR #114 exactly.
- Browser viewport/DOM automation **BLOCKED** in the current container by `net::ERR_BLOCKED_BY_ADMINISTRATOR`, both file and loopback localhost. Do not claim browser/device rendering validated.
- Codemagic API, APK install, checksum verification, signed release and live deployment: **NOT RUN**.

## Safe same-run handoff protocol
1. **Black (builder):** create one bounded feature or evidence-validation source slice on a draft branch, record exact commit/blob SHA; rerun deterministic local tests.
2. **White (review):** independently inspect the committed source and test expectations; note PASS/FAIL/BLOCKED with exact evidence, not a claim of an independently connected phone.
3. **UltraViolet (coordination):** reconcile the canonical [#88](https://github.com/Spiritjcrow/Selma.0/issues/88) queue and resume the next non-conflicting ready item within the *same activation* when permitted. The running platform schedule is unchanged, not a continuously alive agent.
4. On unresolved dependency, mark BLOCKED and pivot to a different scoped task instead of inventing verification.

## Following bounded implementation order
1. Independent browser rendering and keyboard-focus acceptance on Android 11+/13+.
2. Validate 320px, 360px, 768px, 1200px responsive layouts and text contrast; include reduced-motion behavior.
3. Review URL and regex correctness against real anonymized Codemagic logs, avoiding false positives.
4. Read-only import adapter for owner-provided Codemagic build metadata; never send tokens or trigger builds.
5. Local SHA-256 computation of **actual user-selected APK bytes** (separate consent); cross-match its digest with captured build artifact checksum.
6. Package and device smoke test on owned Android hardware; only then consider promotion of claims from recorded to verified.
7. Independent security/privacy review and owner-gated merge/deploy.

## Brand and license
Palette: graphite `#101722`, dark background `#080D15`, modular blue `#0078FF`, cyan `#35D5FF`, orange accents `#FF7A00`. Source icon `assets/icons/evidence-provenance.svg`, original project-specific draft design. Project rights, trademark usage and third-party license compliance require review before public redistribution. No third-party marks added in this increment.

- `python -m unittest discover -s tests -p test_receipt_schema.py -v`: **9/9 PASS** locally using `jsonschema` solely for isolated testing; production has no jsonschema dependency.
- Owner-imported build receipt schema and gated in-memory mapping added; no credentials, HTTP calls or verification state written.