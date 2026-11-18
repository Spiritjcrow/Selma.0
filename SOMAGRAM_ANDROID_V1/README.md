# Somagram for Android (APK preview)

This is a **separate Android native application**, not a Termux app and not the existing Selma companion WebView. It is an early **owner-operated, read-only Telegram account client** built on TDLib.

## Current supported behavior

- Enter Telegram **application** API ID and API hash from [my.telegram.org](https://my.telegram.org) directly in the Android app.
- Enter your own phone number, the Telegram login code, and two-step password when requested.
- Store TDLib session data in private no-backup app storage with a random TDLib database key wrapped by Android Keystore.
- Read the account identity; explicitly request a list of up to **five chat titles**. This does not read individual Telegram messages.
- Works without Termux, root, ADB, developer options, or an external account-management service.

## Not implemented

- Sending, reading, deleting, or forwarding Telegram messages.
- Automatic ChatGPT management of Telegram. There is no direct Telegram connector in this chat; this APK doesn't grant it remote control.
- Sending messages between Black and White or responding to `ping` via the existing Selma Bot. These are separate integration tasks.
- QR login, email login, registration, and other additional auth states; the APK reports them as unsupported rather than trying to bypass Telegram verification.
- Release signing, production review, or confirmed device compatibility.

The app uses a pinned third-party Java TDLib Android binding from the [tdlibx/td source](https://github.com/tdlibx/td). Verify its provenance and release before treating the APK as production-safe. TDLib's documented authorization flow uses [authorization-state updates](https://core.telegram.org/tdlib/getting-started).

## Build without Termux

The GitHub workflow `somagram-android-apk.yml` is designed to run an Android SDK build and upload a **debug APK** with its checksum as a build artifact when the GitHub Actions environment is working.

To run manually in a machine with JDK 17, Android SDK 35, and network access:

```sh
./SELMA0_ANDROID_NATIVE_V1/gradlew --no-daemon -p SOMAGRAM_ANDROID_V1 :app:assembleDebug
```

Expected build output:

`SOMAGRAM_ANDROID_V1/app/build/outputs/apk/debug/app-debug.apk`

The existing Gradle 8.9 wrapper is reused. It is **not** required on the Android phone. The native dependency is downloaded during the build, not during phone login.

If GitHub Actions reports `startup_failure`, that is a hosting/account issue and **no artifact is available**; do not claim an APK exists. The draft PR alone is source, not an installable APK.

## Install and login

Download the debug APK only from your project's successfully completed GitHub workflow artifacts and check its hash. Install manually through Android's normal package-installer prompt. Enter API ID and API hash **on your own phone**. Do **not** enter the BotFather token here. Never post login codes or passwords into chat, Drive shares, tickets, or GitHub.

This debug build is for test accounts/owned devices only. Telegram's safety and security limits continue to apply. Uninstalling the app removes its local session.
