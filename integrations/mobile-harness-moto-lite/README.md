# Mobile Harness Motorola Lite patch (v0.1, source-level)

Target: **Moto G Play (2023), Android 13, 3 GB RAM**. Based on techjarves/Mobile-Harness **v1.0.7** (MIT-licensed source; upstream remains unchanged).

## Two honest execution modes

- **If your Android reports ARM64 ABI (`arm64-v8a`)**: the normal upstream Mobile Harness Ubuntu/PRoot runtime can start, subject to available storage, Android restrictions, and severe 3 GB memory constraints. The patch reduces in-app log/preview/attachment buffers, uses a separate application ID, and displays a light-mode setup warning. No guarantee that Claude agents or Gradle Android builds fit in 3 GB.
- **If your Android is 32-bit (`armeabi-v7a` only)**: a separately compiled JNI ARMv7 carrier lets the app install, but the original ARM64 Ubuntu/PRoot/runtime bundles **cannot run**. Instead of displaying a broken setup wizard, the app opens an explicitly labeled **native offline code/text editor**. It can open local files through Android's Storage Access Framework, edit UTF-8 files up to 256 KB, save a new copy, and preview local HTML without JavaScript or network access. **No fake CLI, agent execution, or APK building** is provided on ARMv7.

32-bit fallback has *not* been verified on physical hardware. No APK is currently included. This is a buildable source modification for Android SDK/NDK CI, not a system image/bootloader mod.

## One command to build (on PC or GitHub Codespaces with internet and Android SDK)

```bash
bash build_moto_lite.sh
```

Optional existing checkout:

```bash
bash build_moto_lite.sh /path/to/Mobile-Harness
```

This clones pinned `v1.0.7`, initializes required submodules, applies a strict, idempotent source transform, then invokes `./gradlew -PmotoLite=true :app:assembleOnlineDebug`.

Prerequisites: JDK 17, Python 3, Android SDK 36, NDK 28.2.13676358, CMake 3.22.1, online Gradle dependency access, and enough disk space for the Android build. Output is `app/build/outputs/apk/online/debug/app-online-debug.apk` if the build succeeds. The release key is **not** included and debug APKs are signed with the builder's debug keystore.

## Security and device limits

- Moto build application ID is `com.jarves.mh.motolite` so it will **not overwrite the official signed application**.
- The custom build disables the upstream automatic update manifest; do not install unaudited updates as if they were signed for this variant.
- **No root, ADB, work-profile admin, or developer options required for installation**; Android must still allow an APK installation from your selected installer.
- Use the **online** flavor, not the 889 MB bundled offline flavor. On ARM64, initial runtime can still consume several GB (the bundled Core runtime alone expands to ~369 MB, plus program data).
- No external accounts needed for offline 32-bit editor. Remote cloud AI/agent providers still need a network and credentials in the ARM64 runtime mode.
- The editor does not modify originals when saving: it uses Android's CreateDocument for a new destination. Keep your sensitive recording files out of untrusted toolchains and cloud services.

## What remains unverified

1. Successful Android compilation and boot on physical Moto G Play 2023.
2. Real ABI capability (`arm64-v8a` vs only `armeabi-v7a`) on this particular Android 13 firmware.
3. Whether the ARM64 runtime remains stable with 3 GB RAM and the phone's storage pressure.

## Legal

Mobile Harness code is MIT-licensed: https://github.com/techjarves/Mobile-Harness/blob/v1.0.7/LICENSE. Third-party component licenses still apply. This patch is a derivative development experiment, not an official Mobile Harness release. Do not assume upstream supports/endorses it.