# No-payment CI fallback for Selma°

## Why this is needed
Issue #26 tracks GitHub Actions runs that fail at admission with zero jobs, before repository code can run. The account currently reports: "The job was not started because recent account payments have failed or your spending limit needs to be increased." Retrying an unchanged run does not test Selma code. GitHub billing and runner admission cannot be repaired by changing test commands.

**Keep this repository private. Do not add a payment method, raise a spending budget, publish source, or weaken branch protection just to run tests.**

## Run the core suite locally (Windows 11, Linux, macOS)
1. Use a complete, trusted **Git checkout** of this private repository on your own computer. Python **3.12+** and Git must be available. The validator rejects a parent/nested pseudo-checkout, requires its own script and test file to be Git-tracked, and refuses a dirty checkout (tracked or untracked files; Git-ignored build products excluded). This is *local provenance checking*, not cryptographic proof of GitHub identity.
2. Install Git Bash on Windows if Bash is missing. No root or phone modifications required.
3. At the repository root, execute:

       python tools/ci_free_local.py

   Optionally copy the exact current commit SHA from PR #89 and pin it with `python tools/ci_free_local.py --expected-sha SHA40`, replacing `SHA40` with the 40 hexadecimal characters. This compares against local `HEAD` but does **not** verify signatures, trusted remote identity, or a fresh fetch. The script runs Python compilation, procurement gate, both unittest suites, support matrix check, **strict JSON validation** (rejects duplicate keys, NaN/Infinity and JSON symlinks), shell syntax checks, and the existing Android-agent loopback smoke test. On Windows it prefers Git Bash over the incompatible WSL Bash launcher.

4. An exit code of **0** with a PASS line means those checks ran successfully *on that machine and checkout*. Exit code **1** is failure; code **2** means a partial result with Bash checks not run. Commands are bounded (core 300s, shell syntax 60s each, smoke 240s). Timeouts trigger best-effort process-tree cleanup; smoke nonzero exit additionally cleans its own group. Windows cannot guarantee cleanup of descendants after the parent process exits. Never substitute that output for a GitHub Actions job ID, signed Git history, or independent review.

## Read-only Android toolchain preflight (no fees)

Before spending time on an APK build, run from the complete repository checkout:

```bash
python tools/selma_android_preflight.py
```

This read-only check reports whether **Java 17+**, the **Android SDK platform 35**, **build-tools 35.0.0**, and the checked-in **Gradle 8.9 wrapper with distribution SHA-256 pin** are present. It fails with a clear prerequisite list and changes no project files. Its checks are covered by `tests/test_selma_android_preflight.py` using synthetic fixtures; they do **not** run a real Gradle build. A preflight PASS is not evidence that dependencies will resolve, tests will pass, an APK will be produced, or a device installation will succeed. The script does not download toolchains, alter account billing, or touch repository credentials.

## Optional debug APK build
Requires Java 17 and an installed Android SDK (set ANDROID_HOME or ANDROID_SDK_ROOT). Gradle may need network access for toolchain dependencies, but it does **not** require paid GitHub Actions minutes.

       python tools/ci_free_local.py --android

Runs `:app:lintDebug`, `:app:testDebugUnitTest` and `:app:assembleDebug` in `SELMA0_ANDROID_NATIVE_V1` with the checked-in Gradle wrapper. It removes only the prior generated `app-debug.apk` and `.apk.sha256` before attempting a fresh build, then requires the new APK to parse as a readable ZIP containing `AndroidManifest.xml`, `resources.arsc`, and `classes.dex`. It hashes the APK in chunks and creates `app-debug.apk.sha256` (digest and filename). Build timeout: 1,800 seconds. These lightweight checks **do not authenticate the APK signature, verify the Android manifest's contents, establish installability, or certify offline behavior**. Do not distribute a debug build as a production release.

## Evidence and next steps
Record the local Git commit SHA, independent expected SHA source (if provided), whether the checkout was clean, command, Python version, OS, exit status, APK SHA-256 and sidecar (if built), and non-sensitive logs in issue #26 or the relevant PR. A summarized three-line PASS message without actual command output and the full 40-character SHA is insufficient to confirm independent execution. Redact local paths, secrets and personal information. Keep #26 open until a real GitHub runner job starts or the owner formally changes the acceptance gates.

If the goal is free automated jobs, a **self-hosted runner** on a dedicated low-privilege, trusted machine may be evaluated; GitHub currently describes self-hosted runner usage as free. It still depends on GitHub admitting jobs, so it is *not* a guaranteed fix for account-wide billing restrictions. Do not register a personal interactive machine as a runner for untrusted PRs.

For restoring GitHub-hosted Actions, check Settings > Billing and licensing > Budgets and usage plus any failed invoice or inherited account policy. GitHub Support can determine whether an account-side restriction is incorrect. The code path in this document works independently of GitHub's Actions service.

## Stop repeated failing notifications
Repository commits to this fallback branch use [skip ci] to suppress push/pull_request workflow runs temporarily. Skipped required checks can remain Pending; do not merge merely because jobs were skipped. This branch remains a review artifact until its checks have been demonstrated outside Actions and accepted by the repository owner.
