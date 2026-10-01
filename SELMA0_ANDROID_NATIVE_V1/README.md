# Selma Native Android — Offline Adult Mode Shell

The native Android shell is now local-first and intentionally refuses a cloud fallback.

It loads only:

`http://127.0.0.1:8765/adult-mode`

from the rootless Selma Termux command core. The WebView blocks navigation and resource requests to non-loopback hosts. Microphone and camera permission requests remain denied until dedicated, explicit offline voice/gaze adapters are implemented.

## Why cleartext HTTP is enabled

Android normally blocks cleartext HTTP. Selma's local command core is intentionally bound to loopback and currently uses HTTP there, so the manifest permits cleartext traffic. The WebView itself then enforces a loopback-only allowlist for navigation and subresources. No hosted `chatgpt.site` URL is used by this shell.

## Runtime dependency

Before opening the APK, start:

~~~bash
$HOME/SELMA0_ANDROID_AGENT_V1/selma0_llama_runtime_android_v1.sh start
$HOME/SELMA0_ANDROID_AGENT_V1/selma0_start_android_v1.sh
~~~

Then the native shell opens the local Adult Mode UI. If the Termux runtime is not answering, the APK shows an offline error page with a retry control rather than switching to a remote service.

## Reproducible build

Install JDK 17, Android platform 35, and Android build-tools 35.0.0. Then run:

~~~bash
./gradlew --no-daemon --stacktrace \
  :app:lintDebug \
  :app:testDebugUnitTest \
  :app:assembleDebug
~~~

The checked-in wrapper pins Gradle 8.9 and verifies the distribution with its published SHA-256 checksum. The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`.

## Current truth state

Implemented in this shell: loopback-only presentation, local Adult Mode page, local chat path, remote-resource blocking, no cloud fallback.

Still separate gates: packaged GGUF weights, production offline ASR/TTS, explicit camera gaze tracking, photorealistic rig/renderer, lip-sync, physical Android FPS/thermal validation, and release signing.
