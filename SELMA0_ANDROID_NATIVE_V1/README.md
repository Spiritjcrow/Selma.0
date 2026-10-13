# Selma Native Android Cloud Build

This minimal native shell loads the private Selma companion over HTTPS. The cloud workflow assembles a debug APK. Microphone, camera, location, background operation, and device administration are not silently granted; Android permission enrollment remains an explicit device-side step.

## Reproducible build

Install JDK 17, Android platform 35, and Android build-tools 35.0.0. Then run:

~~~bash
./gradlew --no-daemon --stacktrace \
  :app:lintDebug \
  :app:testDebugUnitTest \
  :app:assembleDebug
~~~

The checked-in wrapper pins Gradle 8.9 and verifies the distribution with its
published SHA-256 checksum. The debug APK is written to
`app/build/outputs/apk/debug/app-debug.apk`.

## SelmaOS Launcher (opt-in candidate)

This project also contains a native Android HOME activity at
`app/src/main/java/ai/selma/companion/LauncherActivity.java`.
The app exposes **SelmaOS Home** as a separate icon and selectable Android Home app;
it does not silently change the device default. The existing cloud companion
remains a distinct activity. Long-press an installed app in Apps to pin it to
Home. Use System to open ordinary Android settings, safe file selection and
local Selma (provided the Termux runtime is already running).

Launcher architecture, supported scope, accessibility and remaining verification
are documented at `../docs/architecture/SELMAOS_LAUNCHER_V1.md`.

From the repository root, run `python3 -m unittest tests.test_launcher_source_contracts -v`
for source-only guardrails. Then use the Gradle build above and test actual
Home selection and recovery on the owned device. Neither source tests nor APK
compilation by themselves establish physical device compatibility.

## Launcher icons and APK delivery

The debug APK includes **two dedicated offline vector icons**, with no
runtime image fetch, font dependency, or AR capability:

- `@drawable/ic_selma` is the main **Selma** companion app icon.
- `@drawable/ic_selma_home` is the separate **SelmaOS Home** launcher icon.

Manifest and vector-asset source tests:
`python3 -m unittest tests.test_launcher_icon_contracts -v`.

The Android cloud workflow must complete Gradle lint, unit tests, and
`assembleDebug`, verify the APK ZIP and both compiled icon resources using
Android build-tools 35.0.0, then upload the debug APK and its SHA-256 checksum.
Obtain them from the completed successful GitHub Actions **Selma Validation
and Android Cloud Build** workflow's
`Selma-Android-v0.10.0-debug` artifact. A pull request alone is not a
downloadable APK.

**Required before calling this install-ready:** verified successful CI jobs,
APK artifact plus checksum, installation on an owned Android 13+ device,
cold launch, Home selection and reversal, app discovery, offline recovery,
rotation, permission/managed-profile behavior, and restart stability.
An Android debug APK is development-signed, not a production release.

Repository Actions currently has a tracked startup-admission problem in issue
#26. A synthetic `startup_failure` with zero jobs does **not** satisfy any
Android build or installation gate; do not promise a download until an artifact
has actually been produced and verified.
