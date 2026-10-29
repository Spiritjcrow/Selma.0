# SelmaOS Dispatch Bridge — optional single-method owner verification (DRAFT)

Google Drive's current owner-only permissions are separate from app login and **must remain unchanged**. This feature is not a replacement for Drive account access control.

## UX contract
- Display **Choose a verification option** with **Fingerprint**, **Face recognition**, **Voice spectrum verification**.
- User selects one supported, enrolled method and taps **Try this**.
- ONE valid owner-bound proof is sufficient; no requirement to pass two or three methods.
- Failure, timeout, unsupported sensor, cancellation, or unprovisioned verifier leaves the feature LOCKED. Show **Try again new option to verify**. That control resets pending state and returns to the selector.
- No silent fallback to an alternative modality, no text/password bypass invented here. Lock again when the app backgrounds and require server authorization for sensitive operations.

## Security limitations / requirements
- **Android:** Standard BiometricPrompt chooses the biometric modality and does not reliably enforce fingerprint-only vs face-only or tell which enrolled person authenticated. Do not misreport modality-specific verification. Strong biometric plus hardware-backed Keystore owner-account binding is needed; other persons' enrolled biometrics invalidate an exclusive-owner assumption.
- **Voice:** A frequency spectrum, voice transcription, or saved speech sample cannot serve as secure identity proof alone. Voice remains UNAVAILABLE until consent-based enrollment, randomized spoken challenge, anti-replay/deepfake checks, and a vetted speaker-verification provider are independently tested.
- Validate owner binding, challenge nonce, selected method, expiry, rate limits, session revocation, audit; no UI callback, AI text or handoff content grants privileges. Recovery must be owner-approved.
- No Drive sharing, third-party credentials, camera/microphone permissions, live auth, or production access is changed.

## Source slice
- Pure-Java OwnerVerificationGate supports method selection, random 192-bit per-attempt nonce, 45-second TTL, single-method evidence, mismatch/replay/expired-proof rejection, lock/reset and "Try again new option" behavior.
- A trusted ProofVerifier is deliberately UNBOUND. The local test uses a synthetic verifier only. **This slice is NOT an operational fingerprint, face, voice, or owner login implementation.**
- Local javac/java harness result: 21 checks PASS on a standalone source copy. Android Gradle/APK/device/voice/liveness tests NOT RUN. GitHub Actions issue #26 jobs0 remains BLOCKED.
- Next Black: integrate real strongly bound proof provider and UI selector/controls behind an isolated feature gate. White: independently test Android 11/13+ and unavailable modalities. UltraViolet: review identity binding, no bypass, and recovery. #43 remains owned by Sol Red.
