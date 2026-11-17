# Selma° HyperCore | Build Proof Gate v0.2

An Android-friendly, dependency-free **local-only** web prototype for the SelmaOS visual system. Open `index.html` in a browser. The file works without a web server or network, though outbound documentation/build links require connectivity and authentication.

## Implemented (web only)
- Responsive dark blue/orange HyperCore style, cubic core mark and the six original editable vector assets in `assets/icons/`.
- Eight build evidence gates and a local evidence count.
- Save, clear, export and import (size + schema validated) evidence as JSON.
- A copyable pinned native Gradle command and links to GitHub/Codemagic.
- Browser localStorage persistence. No credential or network requests are made by the app.
- Importable `assets/tokens.json` and reusable `assets/hypercore.css` design primitives.

## Deliberately not implemented / not verified
- No Codemagic API, live build, APK download, checksum computation, Android install, evidence authenticity check, or device management.
- The evidence counter indicates only *recorded*, never *verified*, results. All imported/exported records remain unverified.
- No code is injected into the existing Android native application or Termux HTTP runtime. This is a separate reviewable web slice.

## Smoke tests
Run `python3 -m http.server 8766` from this folder, then open `http://127.0.0.1:8766` and test in a browser, or open `index.html` directly. Tests can be run with Playwright against the static page, if available.

## Next integration step
Review the PR; connect actual read-only Codemagic/Android artifact metadata through an authenticated adapter with explicit permission gates and independent digest verification. Do not mark VERIFIED from user-entered text alone.

## 25-point offline preflight (v0.3 draft)

Open [preflight.html](preflight.html) from the same directory as `index.html`. It uses the committed evidence-provenance SVG and checks **25 structural evidence references** across the existing eight local ledger categories. It reads the v0.2 localStorage key, but does not change it. JSON import is in-memory only, and exports exclude raw evidence excerpts. Pattern matches are labelled **RECORDED (UNVERIFIED)**. No network API, tokens, live build or release operation is connected.

Run offline source tests with Node 18+:

```bash
node --check assets/preflight.js
node --test tests/preflight.test.cjs
```

Local authoring result: **36/36 Node tests PASS and 9/9 receipt-schema tests PASS**, exact uploaded source blob SHA matches; Chromium browser route blocked by the execution environment, so **real browser/device acceptance NOT VERIFIED**. See [25-check implementation/handoff map](docs/preflight-25.md).

**Next gated step:** independent Android 11+/13+ browser UI test and permissioned read-only Codemagic evidence adapter. Neither preflight nor saved user references authorize deployment, publishing, merging, APK installation or a claim of machine verification.

### Owner-imported Codemagic metadata (still unverified)

The preflight page also accepts a separate **owner-imported build receipt** with strict project-defined schema `assets/build-receipt.schema.json`. A local parser rejects unknown fields and credential-like additions and maps accepted metadata into the temporary preflight view without modifying localStorage. It does **not** connect to the Codemagic API, prove the provider supplied those values, or verify APK bytes. To run the optional schema tests locally: `python3 -m unittest discover -s tests -p 'test_receipt_schema.py' -v` (requires the `jsonschema` package for tests only).


## v0.6 local test-while-wiring and artifact evidence helpers

Run from `apps/selma-hypercore` on a workstation with Python 3.10+, Node 18+ and optional Python `jsonschema` for schema contract tests:

```bash
python3 tools/run_local_qa.py
```

This fail-closed, one-shot command runs the local Python regression suite, a JavaScript syntax check, then the Node regression suite, stopping at the first failure. Results are JSON on stdout. `--python-only` or `--node-only` are available for constrained systems; skipping one lane does **not** certify the other.

For a **user-supplied Gradle text log**, use:

```bash
python3 tools/classify_gradle_log.py build.log
```

The output distinguishes `REPORTED_FAILED`, `REPORTED_SUCCESSFUL`, `INCOMPLETE_OR_UNKNOWN` and task-level states including `NOT_OBSERVED` and `REPORTED_REUSED`. It never authenticates the runner, reads more than 2 MiB of log text or echoes raw log lines.

For an actual local **APK** and a locally supplied receipt following `assets/build-receipt.schema.json` with `artifact.sha256_claimed`:

```bash
python3 tools/check_apk_receipt.py --apk app-debug.apk --receipt build-receipt.json
```

The SHA-256 is computed incrementally from actual file bytes (1 MiB chunks); filename, byte count and digest must all match the claimed receipt. Return code 0 means **LOCAL_BYTES_MATCH_CLAIM**, 1 means **MISMATCH**, 2 means **ERROR**. This is not independent proof of Codemagic authenticity, build completion, APK safety or Android installation. No uploads, provider API calls, tokens, cost or Android signing are involved.

### Executed evidence (2026-11-16 local authoring environment)
- RED reproduced: older static test expected six icons while the branch includes seven, causing one test failure. Corrected for seven SVG icons and either `aria-label` or valid `aria-labelledby` title references.
- `python3 tools/run_local_qa.py`: PASS; **43/43 Python tests** and **36/36 Node tests**, JavaScript syntax PASS. This is a local test of source reconstructed from the branch and exact SHA-matched new source files; GitHub hosted CI remains NOT_RUN.
- Chromium `page.set_content` acceptance: 25 cards, keyboard focus, 320/360/768/1200 viewport fit, imported receipt, malformed import rejection, summary export without excerpts and no app-initiated requests passed. Direct HTTP/file navigation was blocked by execution policy; real Android browser test NOT_RUN.
- All uploaded new source files and changes read back at their actual GitHub blob SHA. The existing Android project, SDK, Codemagic job, and release pipeline are untouched.

**Current draft-only status:** No APK was provided or hashed during this run; no provider receipt has been authenticated; Android install/smoke, deployment, GitHub Actions runner jobs, publishing and merge remain unverified. Read [the 25-item handoff ledger](docs/next-25-handoffs.json) for next safe work.
