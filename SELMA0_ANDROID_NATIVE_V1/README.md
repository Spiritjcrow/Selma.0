# Selma Native Android Cloud Build

The native Android app now offers two explicit modes:

- **Local Selma + Avatar:** An Android UI with an animated, low-overhead twin-orb avatar. It connects only to `http://127.0.0.1:8765` and sends a chat request when the user taps **Send**. The existing Termux command core provides the model connection, persistent SQLite conversation memory, permission gate, and audit log. There is no new device command executor or privileged permission in the app.
- **Online Companion (HTTPS):** The prior remote WebView, now entered only by an explicit tap. Main-frame navigation is restricted to the exact configured HTTPS host. All WebView device-permission requests continue to be denied.

## Use local mode on Android 13+

1. Install or update the existing local runtime from this repo in Termux. The provided bootstrap script is `SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh`.
2. Start the installed runtime via `~/SELMA0_ANDROID_AGENT_V1/selma0_start_android_v1.sh`. It normally binds to `127.0.0.1:8765`.
3. Start an OpenAI-compatible local model server on `127.0.0.1:8080` for actual offline answers. The Android APK does **not** bundle a model or start a llama.cpp process.
4. Install the native debug APK and tap **Local Selma + Avatar**. Tap **Check local agent** to confirm the server connection.

**Offline privacy caveat:** The backend can fall back to an online model if `SELMA0_ONLINE_BASE_URL_V1` and `SELMA0_ONLINE_MODEL_V1` are configured. The local screen reports this configuration. For strict offline operation, unset the online fallback variables in the Termux server process and verify no network dependency remains. The app itself sends chat requests to loopback only. No guarantee of air-gapped inference is implied when the backend is configured for network fallback.

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
- With online fallback enabled, confirm the UI warns it is configured; with it unset, confirm it does not.
- Verify that cloud mode requires a tap and the native UI does not grant sensitive device permissions.

This is **Fractal Build 01**: a native local-chat/avatar bridge. It is not yet a standalone offline LLM APK, wake-word service, autonomous heartbeat, self-modifying agent, or evidence of consciousness. Kai 9000 is an architectural reference only; no Kai source code has been copied.
