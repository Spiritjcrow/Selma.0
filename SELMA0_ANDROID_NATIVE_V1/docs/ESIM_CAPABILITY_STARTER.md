# Selma Mobile eSIM capability starter (Android)

Scope: read-only device capability detection, with an optional **user-triggered** launch of the operating system's eSIM management screen. Source lives in `app/src/main/java/ai/selma/companion/EsimCapability.java`.

## What exists
- Checks Android 9 / API 28+; the existing project still targets Android 8+ (minSdk 26).
- Checks `FEATURE_TELEPHONY_EUICC` before using `EuiccManager`.
- Checks `EuiccManager.isEnabled()` and returns an explicit availability status.
- Exposes `openSystemManagement(Activity)` as a method for a **future user-visible button**. This method is not called from the current WebView-only `MainActivity`.
- The helper does **not** request new Android permissions or change the manifest.
- No eSIM activation, provisioning, QR scan, carrier account access, local secrets, subscription modifications, or auto-launch.

## Current verification state
| Check | Status |
| --- | --- |
| GitHub source file created on separate branch | PENDING PR / repository verification |
| Java compiler and Android Gradle build | NOT_RUN |
| Unit tests or emulator test | NOT_RUN |
| Android 11+ real-device install and test | NOT_RUN |
| Carrier eSIM entitlement / activation | NOT_ATTEMPTED |

The return value `SYSTEM_MANAGEMENT_AVAILABLE` **only** means Android reports an enabled eUICC service. It is not proof of carrier privileges, an active subscription, or successful activation.

## Acceptance checks for reviewer
1. Verify no permissions or secrets are added and no subscription API mutates the device.
2. Run `cd SELMA0_ANDROID_NATIVE_V1 && ./gradlew --no-daemon :app:lintDebug :app:testDebugUnitTest :app:assembleDebug` on a configured builder.
3. Confirm minSdk 26 paths never call API 28 methods on older devices.
4. In a later independent UI PR, add an explicit user-controlled entry point to `openSystemManagement()`. Verify OS intents on supported and unsupported Android 11+ devices.
5. Record real logs, APK hash, device model/version, and PASS/FAIL only after execution; never infer success from a source diff.

## References
- Android EuiccManager: https://developer.android.com/reference/android/telephony/euicc/EuiccManager
- Android PackageManager FEATURE_TELEPHONY_EUICC: https://developer.android.com/reference/android/content/pm/PackageManager#FEATURE_TELEPHONY_EUICC
- Canonical task ledger: https://github.com/Spiritjcrow/Selma.0/issues/88
