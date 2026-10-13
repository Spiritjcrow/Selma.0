# EmberBot v2.0 Mines Research - recovered build

A **fresh reconstruction**, not a recovery of Kimi's missing source. The pasted assembly script ended in an incomplete UI string. This version prioritizes a buildable, testable Android research companion.

## Implements
- Kivy native Android UI, designed for rootless use (Android API 26+; calculations tested, not device behavior).
- Mines risk estimator for a uniformly random 25-cell board, using exact conditional probabilities.
- Manually logged real-session wagers and actual payouts, tracked profit/loss in satoshis.
- Offline storage under private Android app data; export JSON snapshots to app-private `exports` folder.
- Undo last completed entry; controlled completion and manual verification in the Ember app.
- GitHub Actions lint/test + Android debug APK packaging.

## Explicit limits
- **Does not see undisclosed mine positions, hidden game state, or future random results.**
- **Does not place wagers, connect to Ember, bypass CAPTCHA, or pose as a human.**
- The displayed multiplier is based on a **hypothetical** 1% model edge, **not an Ember payout**. Always log the actual payout from the game.
- Probabilities assume uniform board generation; external fairness verification needs published game data and disclosed seeds.
- No claim of positive expected return or profit.
- JSON export is in the application's private storage; retrieve via appropriate developer file access or future in-app Android share implementation.

## Local test
`python3 -m unittest discover -s EmberBot/tests -v` from repository root.

## Cloud APK build
Open a pull request with `.github/workflows/emberbot-apk.yml` and `EmberBot/`. The workflow runs tests, builds a debug APK on Ubuntu with Buildozer, and uploads the resulting APK as a GitHub Actions artifact. This is an automated pipeline, not a validated device installation.

## Important
In the Kivy UI, `Start Round` only starts a **logging** record. You must play and verify outcomes manually inside Ember itself. Enter the actual cash-out payout received as an integer number of satoshis. The logged balance is a journal, not a wallet balance.

## Five-minute status monitor and immediate continuation

- APK CI is a **dependency chain**: `test` -> `android-apk` -> `verify-artifact`. Each job starts automatically after the preceding job succeeds, subject to runner availability. There is no arbitrary five-minute wait between these steps.
- `.github/workflows/emberbot-monitor.yml` listens for **successful or failed completion** of the named APK workflow (`workflow_run`) and can optionally check status at minutes 2, 7, 12, etc., each hour (12 checks/hour).
- The periodic monitor is **OFF by default**. To opt in, repository owner sets Actions **repository variable** `EMBERBOT_FIVE_MINUTE_WATCH=true` after checking budget/available minutes. This is deliberately a repo variable, NOT a secret.
- GitHub `schedule` and `workflow_run` are recognized only when the monitor workflow file is merged into the **default branch**. Do not merge this draft PR just to enable monitoring; ensure normal reviews and required checks are satisfied.
- The monitor uses **read-only GitHub API calls**. It doesn't restart failing builds, commit fixes, automate gameplay or trigger paid resources by itself.
- A five-minute cron may be **delayed or skipped** by GitHub. On private repos, frequent jobs can consume significant included Actions minutes, resulting in charges if the quota is exhausted.
- **Current blocking issue: [#26](https://github.com/Spiritjcrow/Selma.0/issues/26)**. GitHub Actions returns `startup_failure`, zero jobs, no APK. Fixing repo/account Actions admission/policy/billing is outside the scope of a source-code fix. The monitor cannot resolve that external condition.
- Final acceptance still needs APK installation, Android runtime smoke tests, and verification of actual Ember Mines game fields entered manually.
