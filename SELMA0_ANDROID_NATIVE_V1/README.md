# Selma Native Android Cloud Build

The native Android app now offers two explicit modes:

- **Local Selma + Avatar:** An Android UI with an animated, low-overhead twin-orb avatar. It connects only to `http://127.0.0.1:8765` and sends a chat request when the user taps **Send**. The existing Termux command core provides the model connection, persistent SQLite conversation memory, permission gate, and audit log. There is no new device command executor or privileged permission in the app.
- **Online Companion (HTTPS):** The prior remote WebView, now entered only by an explicit tap. Main-frame navigation is restricted to the exact configured HTTPS host. All WebView device-permission requests continue to be denied.

## Use local mode on Android 13+

1. Install or update the existing local runtime from this repo in Termux. The provided bootstrap script is `SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh`.
2. Start the installed runtime via `~/SELMA0_ANDROID_AGENT_V1/selma0_start_android_v1.sh`. It normally binds to `127.0.0.1:8765`.
3. Start an OpenAI-compatible local model server on `127.0.0.1:8080` for actual offline answers. The Android APK does **not** bundle a model or start a llama.cpp process.
4. Install the native debug APK and tap **Local Selma + Avatar**. Tap **Check local agent** to confirm the server connection.
5. On the same device, switch **off both Wi-Fi and mobile data** and run `python ~/SELMA0_ANDROID_AGENT_V1/selma0_offline_acceptance_android_v1.py --chat` to test a fresh offline-only reply. Without `--chat`, the script checks the status handshake only. It cannot independently verify that the device radios were disabled.

**Strict offline contract:** The local screen requires an updated Termux backend advertising `offline_only_supported: true` and `local_llm_loopback: true`. If either is absent, Send stays disabled. Every native-local chat turn includes `offline_only: true` and `confirmed: true`. The router rejects remote model URLs, refuses HTTP redirects, bypasses environment proxies, and never attempts the configured cloud fallback for these requests. If no local model answers, the UI says unavailable. Cloud fallback remains an explicit possibility for *other clients* and the separate online companion. The local server may itself be a model-proxy executable; only the internet-disabled owned-device test can verify that the actual inference engine is local.

The manifest allows no additional Android permissions beyond `INTERNET`. Cleartext HTTP is permitted only to `127.0.0.1` through a scoped Network Security Configuration; other cleartext endpoints remain blocked. No overlay, microphone, camera, SMS, AR/VR, root, ADB, or developer options are required for this UI.

## Reproducible build

Install JDK 17, Android platform 35, and Android build-tools 35.0.0, then run:

```bash
./gradlew --no-daemon --stacktrace \
  :app:lintDebug \
  :app:testDebugUnitTest \
  :app:assembleDebug
```

The checked-in wrapper pins Gradle 8.9 and verifies its published SHA-256 checksum. The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`.

## Acceptance evidence required

- GitHub Actions must execute a real native Android build job; a queued job or `startup_failure` is not proof.
- Install the APK on the user's actual Android device and confirm animation remains responsive.
- Check that offline agent reports unavailable when the Termux server is stopped and connected when started.
- Verify successful responses from a running on-device model with internet disabled.
- With a cloud fallback configured on the backend, confirm native-local chat still never calls it. Verify the status identifies the strict mode.
- Confirm an older Termux server that lacks the offline-only handshake cannot receive messages from the new local screen.
- Confirm a configured non-loopback model endpoint is rejected before any chat traffic.
- Run the Python regression suite including `test_offline_only_router_v1.py` and `test_native_offline_contract_v1.py`. These are network-free source/unit checks, not Android proof.
- Verify that cloud mode requires a tap and the native UI does not grant sensitive device permissions.

This is **Fractal Build 01**: a native local-chat/avatar bridge. It is not yet a standalone offline LLM APK, wake-word service, autonomous heartbeat, self-modifying agent, or evidence of consciousness. Kai 9000 is an architectural reference only; no Kai source code has been copied.

## GitHub Actions admission blocker

On 2026-10-23, PR #78's earlier run `39869547320` and subsequent run `39974247710` ended with `startup_failure`; no jobs executed. Both the current branch and `main` have the same workflow configuration, and other Selma branches show the same signature. This is tracked in [issue #26](https://github.com/Spiritjcrow/Selma.0/issues/26).

**Owner-side diagnostic order:** (1) check GitHub account billing/payment authorization and Actions quota for private repositories; (2) check repository Actions enablement and policy; (3) provide the two run IDs, synthetic `BuildFailed` path (when reported), and zero-job evidence to GitHub Support if not resolved. Similar failures have been associated with account billing locks, but that cause is **not verified** for this repository. Do not churn workflow YAML or bypass security restrictions merely to fabricate a green check.
