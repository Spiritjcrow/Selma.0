# SelmaOS

Local-first mobile operating environment for Android-native devices and Chromebooks.

## Release candidate components

- `SELMA0_ANDROID_NATIVE_V1/`: native Android 11+ home shell
- `SELMAHOME_ANDROID_V040/`: advanced Android 10+ Home launcher with bundled offline model, local MCP tools, and Workbench
- `SELMA0_ANDROID_AGENT_V1/`: local command core and assistant runtime for Termux
- `SELMAOS_CHROMEOS_V1/`: rootless ChromeOS Linux installer and launcher
- `third_party/open_source_apps.json`: external Termux and F-Droid integrations
- `core/` and `adapters/`: portable capability contracts and platform evidence

The Android shell is selectable as the device Home app and has no remote-login dependency. The Chromebook package runs inside the ChromeOS Linux development environment. Both use the same command core at `127.0.0.1:8765`.

## Implemented core

- Native home screen and installed-app launcher
- Native local chat interface
- Owner-signed Selma Home launcher with bundled CPU story model and loopback-only MCP endpoint
- Persistent SQLite conversation memory
- Strict offline-only inference for native chat
- Loopback-host enforcement, Host validation, origin validation, and redirect denial
- Permission-gated command registry with a hash-chained local audit
- Rootless Termux device bridge and ChromeOS Linux runtime
- User-initiated Termux and F-Droid access without bundled third-party APKs

## Android and Termux

```bash
chmod +x SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh
./SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh
~/SELMA0_ANDROID_AGENT_V1/selma0_start_android_v1.sh
```

Build the native shell with JDK 17+, Android SDK platform 35, and Build Tools 35.0.0:

```bash
cd SELMA0_ANDROID_NATIVE_V1
./gradlew --no-daemon --stacktrace :app:lintDebug :app:testDebugUnitTest :app:assembleDebug
```

Build Selma Home with a retained PKCS#12 owner key:

```bash
ANDROID_JAR="$ANDROID_HOME/platforms/android-35/android.jar" \
ANDROID_BUILD_TOOLS="$ANDROID_HOME/build-tools/35.0.0" \
SELMA_KEYSTORE=/secure/selma-home-owner.p12 \
SELMA_KEYPASS_FILE=/secure/selma-home-owner.pass \
  ./SELMAHOME_ANDROID_V040/build-host.sh
```

## Chromebook Linux

```bash
chmod +x SELMAOS_CHROMEOS_V1/*.sh SELMAOS_CHROMEOS_V1/selmaos-*
./SELMAOS_CHROMEOS_V1/install.sh
~/.local/bin/selmaos-open
```

## Validation

```bash
python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/generate_support_matrix.py --check
bash SELMA0_ANDROID_AGENT_V1/selma0_smoke_test_android_v1.sh
```

Repository checks prove source behavior and the owner-signed APK build. Stable launch still requires handset and Chromebook installation, recovery, endurance, and hardware qualification recorded in `docs/SELMAOS_V1_RELEASE.md`.
