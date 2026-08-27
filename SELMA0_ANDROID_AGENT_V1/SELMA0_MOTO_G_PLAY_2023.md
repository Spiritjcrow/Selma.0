# Selma.0 Moto G Play 2023 profile

This profile deploys the Selma.0 Android Agent V1 command-core runtime to a Moto G Play 2023 through Termux without root.

## Device assumptions

- Android 12+; Android 13 is the validated target for this profile.
- ARM64/aarch64 Termux environment.
- At least 256 MB free before installation. More space is required for any local GGUF language model.
- No Google Play Services for AR dependency.
- No sudo/root requirement.
- Runtime binds to `127.0.0.1:8765` by default.

## What the profile installs

The device-specific installer delegates to the normal Selma.0 Termux bootstrap, then writes a persistent Moto profile and a profile-aware launcher. It runs Python compile validation and the existing command-core software smoke test.

It intentionally does not install TeX Live, Android Studio, Gradle, OpenCV, NumPy, or a large model runtime as part of the core deployment.

## Install from a checkout of this branch

```bash
cd SELMA0_ANDROID_AGENT_V1
chmod +x selma0_install_moto_g_play_2023.sh selma0_validate_moto_g_play_2023.sh
./selma0_install_moto_g_play_2023.sh
```

## Start

```bash
~/SELMA0_ANDROID_AGENT_V1/selma0_start_android_v1.sh
```

Open `http://127.0.0.1:8765` on the phone.

## Validate again

```bash
~/SELMA0_ANDROID_AGENT_V1/selma0_validate_moto_g_play_2023.sh
```

## Language model

Selma's runtime and command core can start without a language model, but conversational inference requires one of these:

1. local OpenAI-compatible inference at `http://127.0.0.1:8080/v1`; or
2. explicitly configured `SELMA0_ONLINE_BASE_URL_V1`, `SELMA0_ONLINE_MODEL_V1`, and optionally `SELMA0_ONLINE_API_KEY_V1`.

A local model is deliberately not downloaded automatically because model files can consume hundreds of megabytes to several gigabytes and the device must retain storage headroom.

## Termux:API

The command core itself does not require root. Hardware features such as Wi-Fi acquisition, notifications, vibration, location, or SMS require the Termux:API companion application and the corresponding Android permissions. Missing hardware permissions do not invalidate the software-only command-core smoke test.
