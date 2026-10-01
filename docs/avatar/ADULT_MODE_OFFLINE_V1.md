# Selma Adult Mode — Offline Avatar Runtime v1

Status: portable runtime increment implemented. Photorealistic rigging, packaged offline ASR/TTS, camera gaze tracking, native overlays, and physical-device performance remain integration work.

## Purpose

Adult Mode is the mature embodied presentation layer for SelmaOS. It must remain usable with networking disabled and must not grant itself device authority. Avatar presentation cannot authorize tools or external effects; those continue through SelmaOS permission, registry, replay-protection, and audit boundaries.

## Baseline identity policy

The stable identity key is `selma.adult.baseline`. Appearance packs may vary clothing, hair treatment, makeup, lighting response, accessibility presentation, and context-specific styling while preserving the approved baseline identity.

Appearance packs are data only. They may not contain executable code, credentials, permissions, or tool authority. Automatic appearance switching is opt-in. Platform adapters must retain a last-known-good pack for rollback.

## Implemented portable primitives

`core/avatar_runtime.py` now provides:

- versioned `AvatarPackManifest` and `AvatarChunkIndex` contracts;
- a detached-signature verification hook that fails closed and can be backed by a vetted platform Ed25519 implementation;
- safe relative-path validation, SHA-256 chunk verification, declared-size checks, decompression ceilings, cancellation, and a byte-bounded lazy LRU cache;
- normalized gaze, expressions, gestures, visemes, mouth-open values, ordered sequence numbers, stale-generation cancellation, and user-priority interruption events;
- deterministic `SoftwareAvatarRenderer` fallback with explicit unsupported zero-copy reporting;
- reusable fixed-capacity scratch buffers that zeroize on release;
- adaptive budgets for FPS, resolution scale, texture quality, animation sampling, expression complexity, audio buffering, cache ceiling, and effects;
- telemetry discipline: missing frame/memory/thermal/battery data causes no inferred performance state;
- a hard kill switch that drains audio, stops capture callbacks and rendering, clears cached avatar chunks, and rejects further animation events.

## Portable acceptance tests

`tests/test_avatar_runtime.py` covers invalid signatures, runtime incompatibility, corrupt chunks, decompression ceilings, bounded caching, cancellation, stale events, interruption/audio drain, software fallback, unsupported zero-copy, buffer reuse/zeroization, kill-switch behavior, and telemetry-only degradation.

## Remaining path to fully offline person-like interaction

1. Voice loop: local VAD/wake, offline ASR, local LLM, offline TTS, barge-in, and viseme timing.
2. Photorealistic rig adapter: skinned body/face mesh, blendshapes, eye saccades, head-follow gaze, breathing, posture, gesture clips, IK, secondary motion, and animation blending.
3. Camera gaze adapter: explicit opt-in local face/eye estimation with visible capture state and immediate disable.
4. Android presentation: rootless foreground overlay, windowed fallback, and separate live-wallpaper adapter.
5. Desktop presentation: Linux/ChromeOS and Windows native presentation adapters.
6. Persistent relationship state: bounded local RAG with provenance, edit/export/delete, corruption recovery, and deterministic restart behavior.
7. Physical acceptance: airplane-mode conversation, restart persistence, interruption latency, memory/FPS/thermal measurements, and kill-switch verification on owned hardware.

No physical-device, photorealistic-rendering, or packaged-offline-voice claim is made by this portable slice.
