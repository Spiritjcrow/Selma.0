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
