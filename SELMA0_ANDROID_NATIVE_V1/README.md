# SelmaOS Native Android Shell

SelmaOS is a small native Android home shell for Android 11+ phones, tablets, and ChromeOS devices with Android app support. It replaces the remote-login WebView with a local launcher, local Selma chat, installed-app access, and user-initiated links to Termux and F-Droid.

## Runtime model

- Package: `ai.selma.companion`
- Minimum Android: API 30
- Target Android: API 35
- Home-screen role: selectable through Android Home settings
- Permissions: `INTERNET` only, used for a fixed `127.0.0.1:8765` bridge
- Cleartext policy: denied globally and allowed only for `127.0.0.1`
- Analytics, advertising, embedded browser login, background service: absent
- Termux and F-Droid: optional external applications; no APK is bundled or silently installed

## Build

Install JDK 17+, Android platform 35, and Android Build Tools 35.0.0, then run:

```bash
./gradlew --no-daemon --stacktrace \
  :app:lintDebug \
  :app:testDebugUnitTest \
  :app:assembleDebug
```

The checked-in wrapper pins Gradle 8.9 and its published SHA-256. Output:

`app/build/outputs/apk/debug/app-debug.apk`

## Device setup

1. Install the SelmaOS APK.
2. Install Termux from F-Droid.
3. Clone or copy this repository into Termux.
4. Run `SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh`.
5. Start `~/SELMA0_ANDROID_AGENT_V1/selma0_start_android_v1.sh`.
6. Open SelmaOS and select **Set SelmaOS as Home**.

The chat interface rejects non-loopback model endpoints in offline-only mode. The default local model API is `http://127.0.0.1:8080/v1`.
