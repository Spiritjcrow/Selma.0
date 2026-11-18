# Selma Adult Mode — Offline Avatar Runtime v1

Status: the local Adult Mode vertical slice is implemented through signed avatar presentation, hard offline-only LLM routing, native Android on-device speech bridging, renderer-neutral embodied motion, and a production rig contract. The final photorealistic 3D asset/renderer, viseme-grade lip sync, camera-based user gaze estimation, and physical-device acceptance remain open gates.

## Purpose

Adult Mode is the mature embodied presentation layer for SelmaOS. It must remain usable with networking disabled and must not grant itself device authority. Avatar presentation cannot authorize tools or external effects; those continue through SelmaOS permission, registry, replay-protection, and audit boundaries.

## Baseline identity policy

The stable identity key is `selma.adult.baseline`. Appearance packs may vary clothing, hair treatment, makeup, lighting response, accessibility presentation, and context-specific styling while preserving the approved baseline identity.

Appearance packs are data only. They may not contain executable code, credentials, permissions, or tool authority. Automatic appearance switching is opt-in. Platform adapters retain a last-known-good pack for rollback.

## Implemented portable runtime

`core/avatar_runtime.py` provides:

- versioned `AvatarPackManifest` and `AvatarChunkIndex` contracts;
- detached-signature verification that fails closed and can use a vetted Ed25519 provider;
- safe relative-path validation, SHA-256 chunk verification, declared-size checks, decompression ceilings, cancellation, and a byte-bounded lazy LRU cache;
- normalized gaze, expressions, gestures, visemes, mouth-open values, ordered sequence numbers, stale-generation cancellation, and user-priority interruption events;
- deterministic software fallback with explicit unsupported zero-copy reporting;
- reusable fixed-capacity scratch buffers that zeroize on release;
- adaptive FPS/resolution/texture/animation/audio/cache/effects budgets driven only by supplied telemetry;
- a hard kill switch that drains audio, stops capture callbacks and rendering, clears cached avatar chunks, and rejects future animation events.

`core/embodied_motion.py` provides deterministic eyes-first gaze, delayed head follow, bounded head mechanics, procedural blink, breathing, torso micro-sway, and speech-driven jaw motion.

`core/rig_binding.py` provides a fail-closed humanoid contract for head/eye/spine/limb bones plus blink/jaw blendshapes, duplicate-binding detection, and recommended viseme channels.

## Android offline path

The rootless Android path now includes:

- `selma0_llama_runtime_android_v1.sh`: managed loopback-only llama.cpp lifecycle with an explicit no-fetch/offline install path;
- `SELMA0_OFFLINE_ONLY_V1=1`: hard policy that prevents configured cloud inference fallback after local failure;
- `selma0_avatar_presence_android_v1.py`: signed-pack verification, bounded archive extraction, explicit first-use trust, rollback, state transitions, local asset serving, and kill/restart controls;
- `selma0_adult_mode_offline_v1.sh`: one-command install/start/launch/status/stop lifecycle for the offline stack;
- local Adult Mode UI at `http://127.0.0.1:8765/adult-mode`;
- native Android shell that blocks non-loopback navigation/resources;
- native speech bridge that uses Android on-device recognition only when the OS reports it available and selects only installed TTS voices whose `networkConnectionRequired` flag is false;
- microphone permission requested only when the user presses Talk; browser-origin camera permission remains ungranted.

The voice lifecycle drives avatar LISTENING → THINKING → SPEAKING → IDLE presentation states. If on-device speech or offline TTS is unavailable, the UI reports that state instead of silently using a remote service.

## Verified fallback appearance pack

A signed `selma.adult.sprite-fallback.v1` pack was built from the existing Selma animation bank. It contains the sprite atlas plus idle, gaze, thinking/waiting, greeting and signed state-map chunks. It is intentionally a degraded 2D fallback, not a claim of final photorealistic 3D rendering.

## Acceptance evidence

Portable tests cover invalid signatures, runtime incompatibility, corrupt chunks, decompression ceilings, bounded caching, cancellation, stale events, interruption/audio drain, software fallback, zero-copy capability reporting, buffer reuse/zeroization, kill-switch behavior, and telemetry-only degradation.

Additional locally executed tests cover:

- eyes-first gaze and delayed head follow;
- bounded head mechanics;
- deterministic blink/motion behavior;
- complete-vs-broken humanoid rig bindings;
- duplicate rig target rejection.

The repository also contains offline-only LLM routing tests and llama lifecycle smoke tests. GitHub Actions currently fails at workflow startup before any job is admitted, so that infrastructure state is not counted as execution evidence.

## Remaining gates to call the full vision finished

1. Produce/import the approved photorealistic Selma GLB/VRM/FBX body and face asset, then satisfy the rig contract.
2. Bind the embodied motion output to the real renderer, skin, eyes, blendshapes, IK, hair/cloth/secondary motion, gesture clips and animation blending.
3. Add phoneme/viseme timing from the final offline TTS path for production lip sync.
4. Add optional camera-based user face/eye estimation only as an explicit local permission, with visible capture state and immediate disable.
5. Package the chosen GGUF and any dedicated ASR/TTS weights for the target hardware, or verify the device-provided offline speech path is sufficient.
6. Run owned-device airplane-mode acceptance: conversation, restart persistence, voice interruption, FPS, memory, thermals, battery behavior and kill switch.
7. Release-sign the APK after those physical gates pass.

Until those gates are evidenced, Adult Mode should be described as a working offline vertical slice with a verified animated fallback, not as the final photorealistic release.
