# SELMA0_BROWSER_COMPANION_V1

Isolated **CAPS-inspired** Chromium Manifest V3 browser companion for Selma°.
The CAPS project by Ari Michael Ayvazyan is Apache-2.0 licensed:
https://github.com/ari-ayvazyan/CAPS-Chromium-AI-Plugin-Skeleton.
This module follows its build→verify→E2E pattern, with a newly authored minimal implementation rather than vendoring upstream code. The original CAPS license and notices remain with upstream. This module is not an upstream CAPS release or an Android Chrome extension.

## Boundaries
- Completely separate directory and feature branch based on `main`. No PR #78 changes.
- Desktop Chromium extension only; **Android Chrome cannot load this desktop MV3 module**.
- No web content scripts, browsing history, tabs, camera, microphone, shell or auto-execution privileges.
- Optional loopback host permission requested **only when user clicks Connect**.
- Gateway is **read-only**, checks an ephemeral session token, sanitizes status, binds 127.0.0.1 only, and never connects to a cloud host.
- The runtime's existing status API exposes private fields; do not call it directly from a browser extension.
- Session secret exists only in browser `chrome.storage.session`; the gateway prints it locally. Do not reuse passwords, API keys or account credentials.
- Local device/desktop processes are not isolated by this gateway; production use needs authenticated backend and local threat-model review.

## Local test (Windows/Linux/macOS desktop)
Requires Node.js 20+, TypeScript and Chromium via Playwright.

```sh
cd SELMA0_BROWSER_COMPANION_V1
npm install
npm run check
npx playwright install chromium
npm run test:e2e
```

Use Playwright Chromium, not branded Google Chrome or Edge: their recent command-line behavior may prevent sideloading.

## Android no-root bridge (desktop to Android Termux)

Prerequisites: user-owned Android phone, Termux runtime listening on **127.0.0.1:8765**, Android USB debugging enabled and desktop ADB authorized by the phone. No root required.

On desktop:
```sh
adb devices
adb forward tcp:18765 tcp:8765
cd SELMA0_BROWSER_COMPANION_V1
node bridge/gateway.mjs
```

The gateway prints a random token. Load `dist/` as an unpacked extension in desktop Chromium, enter the token, click **Connect**, accept loopback host permission, then **Refresh status**. The gateway uses the forwarded port only for Selma's existing `GET /api/selma0/status/v1`. It does not allow chat, tools, SOS, shell commands or writes.

On shutdown: Ctrl+C on gateway; `adb forward --remove tcp:18765`; turn off USB debugging when not needed. **Do not expose ADB or ports 18765/18766 to LAN or internet.**

The Android-native UI and local API remain independent from the desktop extension; the desktop module does not install to Android and makes no assertion about Android APK validation.

## Evidence
- `npm run typecheck` checks TypeScript.
- `npm test` covers gateway authentication, read-only routing, safe response projection and fail-closed errors.
- `npm run build` creates `dist/` for the desktop extension.
- `npm run test:e2e` exercises a real Playwright Chromium extension via a *mock* local Selma status backend. This does not verify physical Android, ADB, or actual Selma runtime availability.
- GitHub Actions are **not required** for local checks; do not confuse missing Actions jobs with successful E2E validation.

## Next gates
1. Run local suite and Chromium E2E on an equipped desktop.
2. Verify real Android Termux + approved ADB forward connection.
3. Review authenticated Android backend and endpoint hardening before any command-capable bridge.
4. Keep PR #78 draft and independent until its physical Android tests and CI acceptance are complete.
