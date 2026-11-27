# SelmaOS v1 Release Candidate

Date: 2026-11-26  
Release: `1.0.0-rc1`  
Stable-launch readiness: **75%**

## Release scope

This release candidate is an Android-native Home shell plus a shared local runtime for Android/Termux and the ChromeOS Linux development environment. It supplies a launcher, local Selma interface, persistent memory, guarded command core, offline inference, and a rootless Chromebook package.

A flashable AOSP or ChromeOS firmware image requires a named device family, bootloader path, kernel and vendor trees, hardware abstraction work, recovery and rollback design, verified-boot signing, and device-specific qualification. Those firmware inputs are not present in this repository. This release gate covers the installable operating environment delivered here.

## Implemented

- Native Android Home and launcher activity for Android 10+ with target SDK 35
- Installed-app launcher with package visibility scoped to launcher apps
- Embedded offline TinyStories 260K inference model and tokenizer
- Local Studio model import, checkpoint staging, validation, activation, and rollback
- Loopback-only, bearer-authenticated MCP server and local Workbench folder review
- Persistent SQLite conversation memory and local safety state
- Rootless Chromebook Linux install, launch, optional user service, and uninstall flows
- Termux and F-Droid as optional external open-source applications
- Host and Termux phone builders, APK verifier, GitHub workflow, and Codemagic workflow
- Owner-controlled PKCS#12 release signing path with the key material retained outside Git

## Evidence completed

| Gate | Result |
|---|---|
| Agent and security tests | 87 passed |
| Repository, platform, CI, and release tests | 61 passed |
| Foundation tests | 2 passed |
| Unique automated tests | 150 passed |
| Stacked runtime smoke probe | Passed; 19 tools registered; no device effects or sensitive scans executed |
| Offline Java probe | Generation, repeatability, checkpoint staging, MCP authentication, discovery, and inference passed |
| Support matrix | Current |
| Clean-revision local CI | Passed at local implementation commit `6183622dcfad56051706e84cd4d00e2e7108d803` |
| Published implementation | Remote commit `19b6b27a04020fd2e9f4bb9c6f3c58cbd2c1bb1a`; Git tree `781b2d9d91dd393cf4a3df8adb07e9c4a1213af6`, identical to the tested local tree |
| Android build toolchain | Official Android SDK Platform 35 r02 and Build Tools 35 |
| Owner APK | `org.selma.home` 0.4.0, version code 5, API 29 minimum, target 35, 1,152,563 bytes |
| APK integrity | ZIP structure, payload digests, binary manifest, DEX header/checksums, signing block, and embedded model license passed |
| Source reproducibility | Recompiled `classes.dex` exactly matches the APK DEX; SHA-256 `b29fc2bc79feb6902e1084ab887ead1f5dcf11c92ffd81033a48051662905359` |
| APK signing | APK Signature Scheme v3 verified; owner certificate SHA-256 `e87d7f0052f8555c97bf75dd6d2475a2cec754c02a8ad0cbb61e377cdd4cbab1` |
| APK checksum | SHA-256 `c95185968d34ec6eeaae567afc4f6055ef9e112ad6e045d2c4710c678ab1a14e` |
| Chromebook package | Installed, launched, returned loopback status, and uninstalled in an isolated Linux home |
| Pull request | [PR 130](https://github.com/Spiritjcrow/Selma.0/pull/130) remains a draft pending hardware qualification |

## Provenance boundary

The recovered `SelmaHome-0.4.0-preview.apk` has a valid v3 signature and internally consistent payload, but its DEX contains `Desktop$2` and `Desktop$Wallpaper`, which are absent from the recovered source snapshot. It is retained only as historical integrity evidence.

The owner APK above was built from the repository implementation, independently verified, and reproduced byte-for-byte at the DEX layer. It is the current release-candidate artifact.

## Readiness calculation

| Area | Weight | Earned | Evidence basis |
|---|---:|---:|---|
| Scope and architecture | 10 | 10 | Platform layout and command-core boundaries are defined |
| Shared runtime and data core | 20 | 18 | Runtime, persistence, embedded model, and checkpoint flow pass tests and smoke probes |
| Android-native system shell | 20 | 15 | Owner-signed APK is built, inspected, and source-reproduced; physical installation remains open |
| Chromebook package | 15 | 11 | Isolated Linux lifecycle passes; real Chromebook integration remains open |
| Security and offline controls | 15 | 14 | Source, runtime, authentication, loopback, and audit tests pass; device review remains open |
| Build and release automation | 10 | 7 | Host and phone builders, local CI, verifier, signing, and hosted pipeline definitions exist |
| Hardware qualification | 10 | 0 | No physical Android or Chromebook evidence is available |
| **Total** | **100** | **75** | **Release candidate; stable launch blocked by hardware and operations gates** |

## Open stable-launch gates

1. Install, upgrade, uninstall, relaunch, select the Home role, and exercise recovery on representative Android 11, 13, 14, and 15 hardware.
2. Run sustained offline generation on handset hardware with networking disabled; record latency, memory, thermals, and failure recovery.
3. Execute the phone-native Termux build and verify its output against the host-built artifact.
4. Verify ChromeOS Android-window behavior and the Linux install/service lifecycle on a Chromebook.
5. Run restart, low-memory, storage-full, battery, accessibility, keyboard, rotation, and multi-window checks.
6. Finalize distribution, privacy disclosure, support lifecycle, signing-key recovery, rollback, incident response, and release operations.

## Hosted pipeline state

The repository workflows now build an ephemeral CI-signed Selma Home APK and run the same structural, signature, source-asset, and DEX reproducibility verifier used locally. Earlier GitHub Actions runs `45821746641` and `45821745617` were rejected before any job step ran because of the repository account billing restriction. This does not replace the successful local clean-revision build.

The draft PR remains unmerged until the physical-device and release-operations gates are recorded.
