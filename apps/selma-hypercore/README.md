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

Local authoring result: **32/32 Node tests PASS**, exact uploaded source blob SHA matches; Chromium browser route blocked by the execution environment, so **real browser/device acceptance NOT VERIFIED**. See [25-check implementation/handoff map](docs/preflight-25.md).

**Next gated step:** independent Android 11+/13+ browser UI test and permissioned read-only Codemagic evidence adapter. Neither preflight nor saved user references authorize deployment, publishing, merging, APK installation or a claim of machine verification.
