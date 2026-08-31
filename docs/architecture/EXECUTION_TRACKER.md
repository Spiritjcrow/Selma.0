# SelmaOS completion execution tracker

Canonical GitHub tracker: issue #17  
Evidence baseline: main at e429da887eb183981d954a39450886b335a5e9b5

| Work package | State | Dependency | Current evidence / next gate |
|---|---|---|---|
| WP-01 Repository baseline | Complete locally | None | Current state, reproduction commands, and all 14 branch dispositions recorded from main e429da8 |
| WP-02 Gate 1 contracts | Implemented locally | WP-01 | Manifest, 10 capability protocols, null adapter, 7 platform manifests, generated matrix, and 15/15 contract tests pass; CI evidence pending |
| WP-03 Offline inference | Pending | WP-02 | Port bounded work from PR #12; prove one real offline answer and cancellation |
| WP-04 Local memory/RAG | Pending | WP-02 | Port PR #6; add provenance, trust, retention, export/edit/delete, recovery |
| WP-05 Voice/interruption | Pending | WP-02, WP-03 | Select licensed ARM64 components and implement the offline turn controller |
| WP-06 Compact avatar | Pending | WP-02, WP-05 | Implement signed packs, bounded reader, state engine, software renderer, and kill switch |
| WP-07 Android/Termux | Pending | WP-03 through WP-06 | Port PR #13/#14 behavior; remove remote-only shell; build and test rootless APK |
| WP-08 Cross-platform | Pending | WP-02, WP-06 | Linux/ChromeOS and Windows first; public-platform limits elsewhere |
| WP-09 Security/autonomy | Pending | WP-02 | Threat model, immediate revocation, audit hardening, and recovery |
| WP-10 Build/release | Blocked | WP-07 through WP-09 | GitHub Actions currently fails before creating jobs; pinned reproducible toolchain required |
| WP-11 Owned-device RC | Blocked | WP-10 | Requires owner-controlled Moto G Play 2023 and manual permission evidence |
| WP-12 Commercialization | Blocked | WP-11 | Requires verified runtime captures and explicit legal/publishing approval |

At every cycle, record changed files, commands, results, blockers, rollback, and the next three actions. Do not mark device, CI, APK, avatar, voice, or offline-model gates complete without direct evidence.
