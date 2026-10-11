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
