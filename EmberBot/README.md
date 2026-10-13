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
