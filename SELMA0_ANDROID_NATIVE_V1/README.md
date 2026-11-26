# Selma Native Android Cloud Build

The Android launcher opens the private Selma companion over HTTPS in the user’s browser. Tap **Open in browser**, then complete ChatGPT sign-in in that browser. The site and its signed-in session stay in the browser.

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
