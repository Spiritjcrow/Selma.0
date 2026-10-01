# Selma Native Android — Offline Adult Mode Shell

The native Android shell is local-only. It loads:

`http://127.0.0.1:8765/adult-mode`

from the rootless Selma Termux command core. The WebView blocks navigation and resource requests to non-loopback hosts. No hosted `chatgpt.site` URL is used by this shell.

## Offline voice

The native bridge does not accept a network speech fallback.

- Talk uses `SpeechRecognizer.createOnDeviceSpeechRecognizer` only when Android reports on-device recognition is available.
- The microphone runtime permission is requested only after the user presses Talk.
- TTS selects only installed Android voices with `networkConnectionRequired == false`.
- Missing offline ASR/TTS is shown as unavailable rather than redirected to a cloud provider.
- TTS lifecycle events drive the local avatar SPEAKING/IDLE presentation state.

Camera permission is not requested by this build. Camera-based user gaze estimation remains a separate explicit opt-in gate.

## Why cleartext HTTP is enabled

Android normally blocks cleartext HTTP. Selma's command core intentionally binds to loopback and currently uses HTTP there, so the manifest permits cleartext traffic. The WebView then enforces a loopback-only allowlist for navigation and subresources.

## Runtime dependency

After the Termux bootstrap, the preferred entry point is:

~~~bash
$HOME/SELMA0_ANDROID_AGENT_V1/selma0_adult_mode_offline_v1.sh launch
~~~

That command forces `SELMA0_OFFLINE_ONLY_V1=1`, starts the local llama.cpp server and Selma command core, verifies that the signed avatar pack is installed, and launches the native shell when Android's `am` command is available.

The lifecycle manager never downloads a model, avatar, voice, or cloud fallback at runtime. Model weights and the signed avatar pack must already exist locally.

## Reproducible build

Install JDK 17, Android platform 35, and Android build-tools 35.0.0. Then run:

~~~bash
./gradlew --no-daemon --stacktrace \
  :app:lintDebug \
  :app:testDebugUnitTest \
  :app:assembleDebug
~~~

The checked-in wrapper pins Gradle 8.9. The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`.

## Current truth state

Implemented: loopback-only presentation, local chat path, remote-resource blocking, hard offline-only inference policy through the Adult Mode lifecycle, signed animated fallback avatar, conditional Android on-device ASR, conditional offline Android TTS, and presentation-state synchronization.

Still gated: final photorealistic rig/renderer, production viseme lip sync, explicit camera user-gaze tracking, packaged GGUF/dedicated speech weights as needed by the target device, physical Android FPS/thermal acceptance, and release signing.
