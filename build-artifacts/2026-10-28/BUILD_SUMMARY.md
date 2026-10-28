# Selma Fractal Build 01 — Cloud build evidence
Date: 2026-10-28
Source: Spiritjcrow/Selma.0 PR #78, commit 63b5f5b81b5cc495b5582211fc5b702655d6a897 (unmodified)
Build environment: ephemeral Vercel Linux Ubuntu 26.04.1, 4 vCPUs, 8 GB RAM, JDK 17, Gradle 8.9, Android SDK Platform 35
Command: gradle --no-daemon --stacktrace :app:lintDebug :app:testDebugUnitTest :app:assembleDebug
Result: BUILD SUCCESSFUL in 51s; 45 actionable tasks, 45 executed; exit code 0.
APK: Selma-0.10.0-debug.apk; 18,726 bytes; package ai.selma.companion; minSdk 26, targetSdk 35; debug signed, APK Signature Scheme v2 verified.
SHA-256: 9249fa22675f091105130eb4afd24a2e24706ff4156ffbfe23f7ff13b1ad9d47
Lint: completed successfully (HTML report remains in ephemeral VM, not part of this archive).
Android unit tests: :app:testDebugUnitTest NO-SOURCE. Zero test cases actually ran.
Warning: MainActivity.java uses/overrides a deprecated API (not a build failure).
Physical installation: not performed.
Backend and genuine offline inference: not performed; require actual Android device and local Termux + local model.
GitHub Actions in repository remain blocked by startup_failure; this is independent Linux sandbox evidence, not repository Actions CI.
This branch is an isolated build-artifacts branch; PR #78 and main were not modified.
