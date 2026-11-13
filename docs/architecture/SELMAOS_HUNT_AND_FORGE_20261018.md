# SelmaOS Hunt & Forge: open-source acceleration and first-boot catalog

**Research snapshot:** 2026-10-18 · **Status:** candidate design and machine-readable catalog, not installed/integrated or release-ready.

## Decision
Build on the existing Selma.0 rootless Android 13+ companion and **opt-in HOME launcher** (draft PR #48). Do not attempt to replace Android kernel/bootloader, transplant Windows/macOS binaries or assets, bypass work profiles, or require AR, root, ADB or Termux. Keep Linux/Chromebook and desktop adapters as independent subsequent stages. A launcher/workspace is not itself a replacement operating system.

**Time saving rationale:** launch and discover independent existing apps now; selectively fork or embed source *only* if a missing user requirement justifies ongoing maintenance, with explicit license review. This can eliminate duplicated file manager, painting, and transfer application development, but completion time has not been measured.

## Repo findings and blockers
- Existing Android HOME/Apps/System launcher work: [PR #48](https://github.com/Spiritjcrow/Selma.0/pull/48). Reuse, do not duplicate. It is not established as merged or device-tested.
- Browser desktop recovery: [PR #45](https://github.com/Spiritjcrow/Selma.0/pull/45). Keep native and browser components separate.
- GitHub Actions startup/admission failure with zero jobs: [issue #26](https://github.com/Spiritjcrow/Selma.0/issues/26). Never interpret zero jobs as passing CI.
- Local HTTP API authentication and independent human approval: [issue #43](https://github.com/Spiritjcrow/Selma.0/issues/43). No sensitive integration via unauthenticated loopback endpoint.
- Coordinator integration and review gates: [issue #17](https://github.com/Spiritjcrow/Selma.0/issues/17). Preserve Black (build) / White (independent QA) / UltraViolet (security/release) roles.

## Proposed boot/setup wizard
1. Welcome, accessibility, language and theme. Explain SelmaOS is an opt-in shell, not a replacement ROM.
2. Device inventory: Android version, storage, permission availability and restrictions. Pure observation only.
3. Local-only/privacy mode ON by default. Cloud fallback always explicitly opt-in; no fixed network identifier, IP, SSID or provider.
4. Choose optional packs: **Everyday essentials**, **Office & planning**, **Drawing & photos**, **Music & recording**, **Device bridge & transfer**, **Security laboratory**. Each checkbox starts unchecked; display install size/permissions after validated metadata is retrieved, not guessed.
5. Display exact upstream program name, publisher, license and link from catalog. Installing opens an approved, user-controlled app store page; **never silent install**. Third-party branding and license notices remain visible. A missing app is listed as 'available to install', never a fake working shortcut.
6. Optional local intelligence: if hardware/storage permits, offer separate llama.cpp and sherpa-onnx adapters after model/weight license, RAM, storage and energy checks; skip cleanly.
7. Preview personalized Start menu, consent summary, exportable local configuration, rollback/restart wizard and ability to choose the system default HOME app.

## Menu layout
- Home, All Programs, Search, Favorites, Running Apps, Settings
- **Productivity:** Notes, Calendar, Documents, Tasks, File Manager, PDF/viewer links
- **Creative:** Paint, Gallery, Media Center, Audio Studio
- **Connectivity:** LocalSend, KDE Connect, owned-device sync and optional cloud links
- **Development:** Editor, log viewer, code repository shortcuts, test harness, local model runner
- **Security:** Permission Inspector, offline audit log, PCAPdroid (only after explicit VPN consent), SBOM/license inventory
- **Recovery:** Backup/export/import, verify checksums, offline help, restore system HOME, diagnostic reports

Items without working implementations must be labeled **planned**, and source apps must retain their actual identities. No default paid add-ons. No background activation. Third-party tools can have distinct privacy/device permissions which require review individually.

## Integration strategy
| Pattern | Decision | Why |
|---|---|---|
| Open verified upstream F-Droid listing | **First** | Minimal maintenance; updates remain signed and managed upstream |
| App discovery / Android ACTION_MAIN + CATEGORY_LAUNCHER | **First** | Expose installed apps without repackaging or copywriting their branding |
| Explicit app-to-app Android intents / SAF file picker | **Second** | Portable capability boundaries; avoid broad filesystem privileges |
| Link separate program with permissioned local API | **Conditional** | Only when upstream supports it and #43 is resolved |
| Fork source and change UX | **Exceptional** | Needs license, attribution, trademark, maintainer, CVE/update and distribution review |
| Copy binaries or resources from Windows/macOS firmware | **Reject** | Not open-source and not conferred by appearance changes |
| Clean-room interoperability research | **Case-specific** | Use permitted documented interfaces and independent code; avoid unauthorized extraction and circumvention |

GPL apps may be used commercially under their terms; when distributing covered modifications, source and copyright-license obligations apply. Separate-process boundaries are *not* a magic automatic GPL exemption. MIT/Apache libraries need their attribution/license obligations, and models/artwork/fonts have **their own** licenses. Verify upstream NOTICE files and transitive dependencies before a commercial release. See [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html) and [AOSP license](https://source.android.com/license).

## Discovery, provenance and security pipeline
`F-Droid signed index / project repository -> identity+license scanner -> provenance register -> compatibility/permission filter -> human-reviewed candidate -> Black prototype -> White tests -> UltraViolet audit -> owner-approved release`.

Do not use the F-Droid display-only API for APK authenticity. Verify signed repository index and APK signer; pin package IDs/signature expectations; build a CycloneDX SBOM. Record source URL, commit/tag, SPDX identifier, dependency tree, known CVEs, permission deltas, build reproducibility, supplier and rollback mechanism. No private asset bulk export to third-party services. External collaborators only receive authorized scoped documents.

## Android acceptance matrix
Rootless Android 13–17 (where devices available), work-profile/MDM restrictions honored, Android permissions and default HOME choice user-controlled, no AR/ADB/root required, storage pressure and memory limits handled, zero-network startup, changed Wi-Fi / reconnect state, screen-reader and physical buttons, uninstall/revert to original launcher, no unapproved network traffic. These are **test requirements**, not passing tests.

## Immediate staged delivery (dependency-correct)
1. Extend PR #48 with an optional catalog reader + testable first-boot pack selection and user-owned links. Do not merge stale PR code unreviewed.
2. Add manifest contract tests: duplicate IDs, missing license, invalid URL, checked-by-default, silent install, unknown permission, metadata staleness, no signature verification, and device-policy restriction must all fail closed.
3. Repair or conclusively escalate Actions admission in #26; fix auth in #43 before command integration. Observe real CI jobs and builds.
4. Add platform-neutral connectors for local-model inference and speech only after bench+license checks, respecting #17 release gates.
5. Complete Android owned-device acceptance, signed APK update/rollback test, provenance/SBOM and copyright/trademark review.

## Official evidence (current research)
- [F-Droid repo index/signature/API warning](https://f-droid.org/docs/All_our_APIs/)
- [Fossify releases/apps](https://www.fossify.org/install/)
- [KDE Connect Android](https://f-droid.org/en/packages/org.kde.kdeconnect_tp/)
- [LocalSend](https://f-droid.org/en/packages/org.localsend.localsend_app/)
- [PCAPdroid](https://f-droid.org/packages/com.emanuelef.remote_capture/)
- [llama.cpp Android](https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md)
- [sherpa-onnx Android](https://github.com/k2-fsa/sherpa/blob/master/docs/source/onnx/android/build-sherpa-onnx.rst)
- [CycloneDX specification](https://github.com/CycloneDX/specification)

## Collaboration (proposed, not connected)
Devpost for optional demonstration/submission; SciSpace for architectural review; Figma for first-boot prototype; Dropbox/Drive for owner-approved artifacts; Slack/Rovo for human-approved task handoffs; Runway for original promotional/demo media; Superpowers only after its actual capabilities are identified. These integrations are NOT asserted active or authorized in this PR. No developers were contacted or emailed.

**Machine-readable companion:** `docs/architecture/selmaos_optional_app_catalog_v1.json`.
