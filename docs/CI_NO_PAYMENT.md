# No-payment CI fallback for Selma°

## Why this is needed
Issue #26 tracks GitHub Actions runs that fail at admission with zero jobs, before repository code can run. The account currently reports: "The job was not started because recent account payments have failed or your spending limit needs to be increased." Retrying an unchanged run does not test Selma code. GitHub billing and runner admission cannot be repaired by changing test commands.

**Keep this repository private. Do not add a payment method, raise a spending budget, publish source, or weaken branch protection just to run tests.**

## Run the core suite locally (Windows 11, Linux, macOS)
1. Use a complete, trusted **Git checkout** of this private repository on your own computer. Python 3.12+ and Git must be available. The script prints the exact commit; if tracked files are modified, it warns that the commit alone is insufficient provenance.
2. Install Git Bash on Windows if Bash is missing. No root or phone modifications required.
3. At the repository root, execute:

       python tools/ci_free_local.py

   The script runs Python compilation, procurement gate, both unittest suites (including the local-runner regression tests), support matrix check, **strict JSON validation** (rejects duplicate keys, NaN/Infinity and JSON symlinks), shell syntax checks, and the existing Android-agent loopback smoke test. On Windows it prefers Git Bash over the incompatible WSL Bash launcher.

4. An exit code of **0** with a PASS line means those checks ran successfully *on that machine and checkout*. Exit code **1** is failure; code **2** means a partial result with Bash checks not run. Commands are bounded (core steps 300 seconds each, individual shell syntax checks 60 seconds, smoke test 240 seconds). Timed-out descendant processes are terminated to avoid orphaned test services. Never substitute that output for a GitHub Actions job ID or a verified independent review.

## Optional debug APK build
Requires Java 17 and an installed Android SDK (set ANDROID_HOME or ANDROID_SDK_ROOT). Gradle may need network access for toolchain dependencies, but it does **not** require paid GitHub Actions minutes.

       python tools/ci_free_local.py --android

Runs :app:lintDebug, :app:testDebugUnitTest and :app:assembleDebug in SELMA0_ANDROID_NATIVE_V1, using only the checked-in Gradle wrapper (fails closed if its JAR is absent). The Android build has a 1,800-second timeout and streams the debug APK's SHA-256 without loading the whole file into memory. A successful build is **not** a device-installation or offline-behavior pass. Do not distribute the debug APK as a production signed release.

## Evidence and next steps
Record the git commit SHA, whether the checkout had tracked modifications, command, Python version, OS, result, APK SHA-256 (if built), and relevant non-sensitive test output in issue #26 or the relevant PR. Redact local paths, secrets and personal information. Keep #26 open until a real GitHub runner job starts or the owner formally changes the acceptance gates.

If the goal is free automated jobs, a **self-hosted runner** on a dedicated low-privilege, trusted machine may be evaluated; GitHub currently describes self-hosted runner usage as free. It still depends on GitHub admitting jobs, so it is *not* a guaranteed fix for account-wide billing restrictions. Do not register a personal interactive machine as a runner for untrusted PRs.

For restoring GitHub-hosted Actions, check Settings > Billing and licensing > Budgets and usage plus any failed invoice or inherited account policy. GitHub Support can determine whether an account-side restriction is incorrect. The code path in this document works independently of GitHub's Actions service.

## Stop repeated failing notifications
Repository commits to this fallback branch use [skip ci] to suppress push/pull_request workflow runs temporarily. Skipped required checks can remain Pending; do not merge merely because jobs were skipped. This branch remains a review artifact until its checks have been demonstrated outside Actions and accepted by the repository owner.
