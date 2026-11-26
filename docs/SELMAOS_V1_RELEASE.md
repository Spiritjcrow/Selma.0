# SelmaOS v1 Release Candidate

Date: 2026-11-26  
Release: `1.0.0-rc1`  
Stable-launch readiness: **63%**

## Release scope

This release candidate is an Android-native Home shell plus a shared local runtime for Android/Termux and the ChromeOS Linux development environment. It supplies a launcher, local Selma interface, persistent memory, guarded command core, and rootless Chromebook package.

A flashable AOSP or ChromeOS firmware image requires a named device family, bootloader path, kernel and vendor trees, hardware abstraction work, recovery and rollback design, verified boot signing, and device-specific qualification. Those firmware inputs are not present in this repository, so the release gate measures the installable operating environment delivered here.

## Implemented

- Native Android Home and launcher activity for API 30 through target API 35
- Installed-app launcher with Android package visibility scoped to launcher apps
- Native Selma chat over a fixed `127.0.0.1:8765` bridge
- Strict offline-only inference for native chat and command-core chat by default
- Loopback bind enforcement, proxy bypass, redirect denial, Host checks, origin checks, bounded HTTP responses, permission gates, and hash-chained audit records
- Persistent SQLite conversation memory and local safety state
- Rootless Chromebook Linux install, launch, optional user service, and uninstall flows
- Termux and F-Droid as optional external open-source applications
- Local CI, Android preflight, GitHub workflow, and Codemagic workflow definitions

## Evidence completed

| Gate | Result |
|---|---|
| Agent and security tests | 87 passed |
| Repository, platform, CI, and release tests | 57 passed |
| Unique automated tests | 144 passed |
| Stacked runtime smoke probe | Passed; 19 tools registered; no device effects or sensitive scans executed |
| Support matrix | Current |
| JSON and shell validation | Passed |
| Clean-revision local CI | Passed at local commit `6eb987cc50c5f1210bb42c7fbdd4e0d2a42b8f19` |
| GitHub release tree | `8245d91f92d67d2254dbefb216ed98b749125bdc`, identical to the locally tested tree |
| Chromebook package | Installed, launched, returned loopback status, and uninstalled in an isolated Linux home |
| Pull request | [PR 130](https://github.com/Spiritjcrow/Selma.0/pull/130) at remote commit `e09a41d7242f5445afc216b1d1a8843ae14164ba` |

Public Slack search returned no SelmaOS requirements or earlier application selections. The release therefore uses the two project-compatible open-source applications recorded in `third_party/open_source_apps.json`.

## Readiness calculation

| Area | Weight | Earned | Evidence basis |
|---|---:|---:|---|
| Scope and architecture | 10 | 10 | Platform layout and single command core are defined |
| Shared runtime and data core | 20 | 16 | Runtime and persistence pass tests and smoke probe; an on-device model binary and model profile remain external |
| Android-native system shell | 20 | 10 | Source and contracts pass; APK compilation and installation remain unverified |
| Chromebook package | 15 | 11 | Generic Linux lifecycle passes; real Chromebook integration remains unverified |
| Security and offline controls | 15 | 13 | Source and runtime security tests pass; device security review remains open |
| Build and release automation | 10 | 3 | Pipelines and local preflight exist; hosted runners did not execute and no release artifact exists |
| Hardware qualification | 10 | 0 | No physical-device evidence was available |
| **Total** | **100** | **63** | **Release candidate; stable launch blocked** |

## Open stable-launch gates

1. Build `lintDebug`, unit tests, and the APK with an official Android SDK 35 and full JDK 17+.
2. Inspect APK entries, manifest, debug signature, size, and SHA-256 sidecar.
3. Create the release signing path and generate a signed release artifact under owner-controlled keys.
4. Install, upgrade, uninstall, relaunch, and select the Home role on Android 11, 13, 14, and 15 hardware.
5. Verify local chat while network access is disabled and a loopback model server is running.
6. Verify Termux and F-Droid launch/install fallbacks without mixing Termux signing sources.
7. Verify ChromeOS Android-window behavior and ChromeOS Linux install/service behavior on a Chromebook.
8. Run restart, low-memory, storage-full, battery, accessibility, keyboard, rotation, and multi-window checks.
9. Resolve release notes, privacy disclosure, support lifecycle, rollback procedure, and distribution channel.

## External build blockers observed

- The current execution environment lacks an Android SDK platform and a full JDK with `javac` and `jlink`; the read-only preflight blocked before attempting a build.
- GitHub Actions runs `45821746641` and `45821745617` failed at runner admission with zero executed steps, consistent with the repository's documented account billing restriction.
- Codemagic reached its GitHub login screen without an authenticated session, so no build was started.

The draft PR remains unmerged until the binary and physical-device gates are recorded.
