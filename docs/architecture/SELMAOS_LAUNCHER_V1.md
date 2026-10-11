# SelmaOS Launcher V1: home screen and system layout

**Status:** opt-in candidate implemented as source on a feature branch. Android SDK builds and device usability tests have not yet been verified. This is an Android HOME app, not a privileged OS replacement.

## Experience architecture

SelmaOS uses a single-thumb navigation model: fixed Selma summon button, calm visual hierarchy, predictable Home/Apps/Work/System tabs, and user-assigned local workspaces for organizing installed apps. No AR or VR is necessary.

| Layer | Function | Source implementation now | Planned next |
| --- | --- | --- | --- |
| Home | Daily starting point | Clock, date, assistant entry, pinned apps, shortcuts | Role-priority cards chosen explicitly by user |
| Apps | Discover and open installed apps | PackageManager launcher query, case-insensitive search, visible pin/unpin and workspace controls, launch | Category filters, multi-profile handling |
| System | Rootless device functions | Wi-Fi panel, Bluetooth settings, system settings, document picker, appearance toggle, HOME selection | Permission center, trusted-device status, power diagnostics |
| Assistant | Access Selma | Launch loopback browser at 127.0.0.1:8765, manual cloud companion option | Native on-device status, models, VAD, TTS, voice/face/avatar controls |
| Workspace | Organize productive apps | Local Build/Connect/Secure/Daily categories with app assignments saved across restarts | GitLab/GitHub, tasks, terminal, developer tools, design, CAD adapters |
| Files and Vault | Storage and backups | Android picker only | Nextcloud, verified SFTP, encrypted archive, key protection |
| Communications | Device handoff | Not implemented | KDE Connect, Matrix, consented messaging |
| Safety | User control | No new safety permissions | Trusted devices, incident records, opt-in emergency workflow |
| Automation | Authorized workflows | No new executor | Scope, timeouts, queue, cancellation, audit, retries |
| Accessibility | Efficient use | Large touch areas, visible pin/workspace controls, contrast, descriptions | Text scaling, focus navigation, reduced motion |

## Present functionality and interaction

- SelmaOS Home is exposed both as a launchable app icon and as an eligible HOME activity. User chooses the default Home app. No automatic takeover.
- Existing remote HTTPS companion activity is preserved separately.
- Installed-app enumeration is limited to discoverable Android launcher activities with manifest queries. No broad app enumeration permission or device administration.
- Favorites are stored in app-private SharedPreferences. Visible star actions pin/unpin apps, with long-press also supported. Favorites display on Home.
- A fourth Work tab groups already-installed apps into Build, Connect, Secure, and Daily, with explicit assignment and removal dialogs. Workspace assignments are local and do not install apps, change permissions, or contact services.
- Active tab and selected workspace restore after rotation/activity recreation.
- Home shows a live TextClock and current calendar date; theme switching stays local.
- System tiles launch official Android settings or the Android Storage Access Framework file chooser, not hidden privileged actions.
- Local Selma opens an external browser pointed at http://127.0.0.1:8765. This does not check whether the local runtime has been started.
- The launcher does not request microphone, contacts, location, SMS, accessibility service, notification listener, root, Shizuku, VPN, wireless debugging, or device-owner privileges.
- This source is not proof of an APK build, successful real-device launch, background agent, verified voice synthesis, or widget host support.

## Selected third-party integration paths

**First future adapters:** KDE Connect, Nextcloud stable, SFTP-SAF, Share to Folder, Markleaf, jtx Board, Gitalchemy, Nightbell, PGPony and Privamatic.

**Conditional research:** HTTP Request Shortcuts (API-token scopes), Mages (Matrix interoperability), Tinc Mesh (VPN collisions), Marmalade TTS (review anti-features), Scrib (current device incompatibility). Avoid mandatory Shizuku or root dependence.

**No direct access claimed:** Third-party applications must be installed, consented and provide compatible interfaces. Descriptions alone do not prove supported integration or security.

## Control boundaries

1. Route any newly implemented device effects through the existing permission engine, audited tool registry, and platform-neutral capability contracts; do not introduce a parallel unrestricted executor.
2. Do not bypass Android policy, secure lock screen, work profiles, VPN limitations, authentication, key stores, or managed-device restrictions.
3. Never expose wallets, passwords, 2FA, SMS, health records, or cryptographic keys through app search. Review permissions and data retention per adapter.
4. Use SSH host-key checks or verified TLS for remote files, with user-controlled encrypted backups before deletion.
5. Build multi-network adaptive connectivity without hardcoding any SSID, IP, carrier or router.
6. Keep the stock launcher available. Users must be able to revert to it if SelmaOS crashes or has regressions.
7. No automatic third-party installation or external service sign-in.

## Verification gates

1. Android SDK 35 and JDK 17: run :app:lintDebug, :app:testDebugUnitTest, :app:assembleDebug. GitHub Actions startup failures do not count as successful checks.
2. On a Moto G Play 2023 with Android 13, test setting Home by user choice, reverting to the old launcher, app discovery, launch, search, pin/unpin, offline state, device policy, orientation, low storage, accessibility.
3. Profile responsiveness and background battery use; test low-end graphics.
4. Improve accessibility: validate the newly added visible pin/workspace controls using TalkBack; add text-scale controls, keyboard navigation, and language localization.
5. Add an adapter status and authorization panel before connecting outside apps or privileged workflows.

## Launcher V1.1 source update

- Commit on draft PR #48 adds Home/Apps/Work/System navigation, visible per-app pin and workspace controls, and locally persisted assignment categories.
- Python contract tests now assert workspace persistence markers, visible controls and accessible descriptions. Source checks are guardrails, not Android compilation or accessibility acceptance.
- No external adapter has been activated; still awaiting a successful Android SDK build and Motorola device test.
