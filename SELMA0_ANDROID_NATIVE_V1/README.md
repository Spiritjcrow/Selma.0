# SELMA0 Android Native V1

This is the first rootless native Android shell for Selma.0. It targets Android 12+
(`minSdk 31`) and preserves the existing Termux/Python runtime as a device-local
worker at `http://127.0.0.1:8765`.

## Implemented in this milestone

- Kotlin and Jetpack Compose application shell
- user-started foreground service with a persistent notification
- summon-only `TYPE_APPLICATION_OVERLAY` Selma avatar
- fixed loopback status and chat client; arbitrary URLs and commands are rejected
- explicit notification and overlay permission flows
- validated six-frame Selma active-work animation derived from the repaired v2 sprite sheet
- CI tasks for lint, JVM unit tests, and debug APK assembly

## Deliberate degraded modes

- If Termux Selma is not running, the app stays usable and reports the unavailable
  local runtime without silently falling back to the internet.
- The overlay remains disabled until the user grants Android's display-over-other-apps
  permission and explicitly summons Selma.
- Wakeword, microphone foreground-service type, llama.cpp, NDK/JNI, semantic RAG,
  release signing, and Play distribution are not claimed by this milestone.

## Build

Use JDK 17 and Android SDK 36:

```bash
./gradlew :app:lintDebug :app:testDebugUnitTest :app:assembleDebug
```

Expected APK:

`app/build/outputs/apk/debug/app-debug.apk`

## Safety and privacy boundary

The native shell talks only to fixed loopback endpoints. It contains no root request,
general shell executor, background microphone capture, remote server, analytics SDK,
or committed credential. The foreground service starts only from visible user action.
