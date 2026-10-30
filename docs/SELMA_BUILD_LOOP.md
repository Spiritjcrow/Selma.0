# SelmaOS bounded local build-on-commit loop (v0.1)

**Status:** experimental review-only helper, stacked on the no-payment local CI fallback in PR #89. Does **not** bypass GitHub Actions account restrictions (#26). Does **not** assert an Android APK was built, installed, or approved.

## Purpose

Use a trusted local Git checkout to repeatedly execute existing source validations (and, optionally, a *debug* APK build) whenever the checkout advances to a new **clean, committed** HEAD. This speeds iteration without touching native UI PR #78 or security PR #86.

There is **no AI code authoring, self-modifying executable, self-deployment, background cloud daemon, Play Store release, auto-merge, credential access, or production signing** in this version. A future proposal-producing agent must operate in its own sandbox/branch with reviewed diffs, tests and an explicit merge/release decision.

## Prerequisites

- Owner-controlled Windows/Linux/macOS computer; trusted complete checkout of the private repository; Git and Python 3.12+.
- For full core checks: Bash (Git Bash preferred on Windows) and dependencies described in docs/CI_NO_PAYMENT.md.
- For Android: Java 17, Android SDK, and trusted repository Gradle wrapper. This may download dependencies but does not require paid GitHub Actions minutes.
- This branch depends on PR #89's tools/ci_free_local.py; do not attempt to run on an unrelated branch.

## Usage from the repository root

Run once:

~~~sh
python tools/selma_build_loop.py
~~~

Also build a debug APK:

~~~sh
python tools/selma_build_loop.py --android
~~~

Bounded watch mode (up to three clean commits or 60 minutes, whichever comes first):

~~~sh
python tools/selma_build_loop.py --watch --max-runs 3 --max-minutes 60 --interval 20 --android
~~~

Watch mode works only while this command is running on that machine. It does not start itself, push to GitHub, open PRs, or persist beyond the process. An hourly ChatGPT automation is not an active local executor.

## Kill switch and locking

Create a file named SELMA_BUILD_STOP inside the actual Git control directory to request termination of an active local validation.

~~~sh
# Linux/macOS/Git Bash on a conventional checkout
touch .git/SELMA_BUILD_STOP
# When intentionally resuming:
rm .git/SELMA_BUILD_STOP
~~~

~~~powershell
New-Item -ItemType File .git\SELMA_BUILD_STOP
# When intentionally resuming:
Remove-Item .git\SELMA_BUILD_STOP
~~~

An exclusive SELMA_BUILD_LOCK in the Git control directory prevents overlapping instances on the same checkout. If the process crashes and the lock persists, inspect whether it is still running before removing the stale lock.

The process fails closed for a dirty checkout, malformed SHA, missing validator, nonzero or partial result, source mutation during validation, kill switch, existing lock, or deadline overrun. Stop/timeout exit statuses are nonzero. Run only trusted source in a low-privilege environment.

## Evidence and Play Store gates

The controller's own 11 isolated synthetic fixture tests passed on 2026-10-30 using unittest discover in a separate test workspace. These are NOT evidence that the complete private Selma checkout, Android Gradle build, or a device test succeeded.

1. Independently run the complete checkout tests on the proposed SHA, preserving exit codes, OS/toolchain details, and redacted logs.
2. Compile and hash an Android debug APK. Test installation and responsiveness on an owner-controlled Android 13+ device.
3. Resolve #43: authenticated local clients and trusted UI-bound approvals; caller-supplied boolean flags are not authorization.
4. Verify #78 strict offline behavior with internet disabled and an actual local model. Keep #86's HMAC proposal out of production pending signing-key, replay-persistence, and runtime work.
5. Obtain a real executed CI job or an explicitly authorized and documented release-gate exception, then independently review, create a protected signed Android App Bundle, satisfy Google Play policy/listing requirements, perform limited testing, and only then roll out.

**Safety boundary:** the helper never authorizes autonomous merge, production credentials, paid GitHub changes, Play submission, advertising purchases, or financial transactions.
