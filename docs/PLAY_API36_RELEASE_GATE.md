# SelmaOS Play release compatibility gate — API 36 proposal

As of 2026-10-30, Google Play requires API 36 for new ordinary Android apps (effective 2026-08-31, with possible account-specific extension through 2026-11-01). The avatar branch PR #78 previously used compileSdk/targetSdk 35 and Android Gradle plugin 8.7.3, so its unchanged Android build is not a current submission candidate.

This isolated, DRAFT-only branch stacks on PR #78, keeps its native code, runtime, strict offline chat contract, and manifest permissions unchanged, and proposes:
- compileSdk 36; targetSdk 36; minSdk remains 26; applicationId/version unchanged.
- Android Gradle Plugin 8.10.1 (AGP 8.10 supports API 36).
- Gradle 8.11.1 with Gradle's published binary distribution SHA-256 f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6.

Authoritative references:
- https://support.google.com/googleplay/android-developer/answer/11926878
- https://developer.android.com/build/releases/agp-8-10-0-release-notes
- https://gradle.org/release-checksums/

## Required validation on a trusted complete checkout

1. Install JDK 17, Android platform 36 and build tools; inspect Gradle wrapper JAR and regenerate/verify it with the trusted Gradle 8.11.1 distribution as appropriate. The existing checked-in wrapper JAR was generated for the older wrapper version; its compatibility and supply-chain provenance must be checked before claiming the wrapper is updated end-to-end.
2. From SELMA0_ANDROID_NATIVE_V1, execute Gradle wrapper validation and --no-daemon :app:lintDebug :app:testDebugUnitTest :app:assembleDebug :app:bundleRelease. Keep any unsigned release bundle internal; do not distribute it.
3. Verify output APK/AAB ZIP structure, signing status, manifest target SDK, reproducible versionCode, dependency availability, and redacted logs.
4. Install on owned Android 13+ devices; test API 36 behavior changes, display/edge-to-edge/navigation, memory pressure, offline strict local model routing, backend failure behavior and user-consent boundaries.
5. Resolve #43 caller authentication/approval vulnerabilities, confirm Play privacy/data safety, verify device user protection; secure upload key and identity/package registration before production submission.

## Evidence status

Only source configuration changes have been committed in this branch. No Gradle execution, actual Android SDK 36 installation, App Bundle signing, Play Console upload, on-device test, or user-visible release has been performed. GitHub Actions admission is still blocked at #26. This is a release compatibility **proposal**, not a proven build or Play-approved application. PR #78 is left untouched.
