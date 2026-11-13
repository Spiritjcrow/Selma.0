# SELMA0_NETHUNTER_CATALOG_V1

## Purpose

Integrate the official Kali NetHunter Android Store into the existing Selma.0
permissioned command-core registry as a **metadata-only** application catalog.

Source: https://store.nethunter.com/repo/
Official signing-key fingerprint as listed by the repository:

FE 7A 23 DF C0 03 A1 CF 2D 2A DD 24 69 B9 C0 C4 9B 20 6B A5 DC 9E DD 65 63 B3 B7 EB 6A 8F 5F AB

NetHunter Store is F-Droid based. Its published index may contain outdated
applications, APKs, dependencies, and device restrictions. Reviewing a package
listing does not establish safe installation or Android 13 compatibility.

## Registered commands

Commands are available through the existing Selma.0
POST /api/selma0/tools/execute/v1 route:

- nethunter.catalog_sync: approved external_effect command. Retrieves
  fixed-origin official metadata over HTTPS and caches a bounded, sanitized
  inventory to ~/.selma0/nethunter/catalog-v1.json.
- nethunter.catalog: read command; optional arguments query and limit.
  Searches the local cache. Empty cache returns a clear readiness message.
- nethunter.package_details: read command; argument package_id.
  Returns the package's listing and official information page.

All applications present in the fetched index become **discoverable**
automatically. There is no assumption that they are installed, functional,
device-compatible, or approved as executable Selma capabilities.

Example:
POST /api/selma0/tools/execute/v1
Content-Type: application/json

{"tool":"nethunter.catalog_sync","approved":true,
 "request_id":"explicit-unique-user-sync-001","arguments":{}}

Then use:
{"tool":"nethunter.catalog","arguments":{"query":"terminal"}}

Use a new request_id for a new authorized sync. The existing Selma audit log
and idempotency rules apply to the external-effect command.

## Trust boundaries

This connector **does not verify the signed F-Droid index**, and must not be
used to approve APK installation automatically. HTTPS metadata is advisory,
not a signed software supply-chain attestation. Use the official NetHunter
Store app or F-Droid client for signature verification and installation;
confirm the repository key fingerprint from the official page.

No remote shell, dynamic code execution, APK downloader, package installer,
kernel modification, USB gadget control, Wi-Fi injection, network scanning,
credential access, exploit launch, or autonomous reconnaissance is exposed.

Do not run commands found in descriptions; treat upstream metadata as
untrusted. User-owned lab and approved security work can later have separate
small, audited, task-specific adapters with explicit scope, target and
runtime capabilities, rather than auto-registering arbitrary programs.

## Android compatibility

- Android 13+, stock/unrooted: compatible with **NetHunter Rootless** via
  Termux, subject to storage/RAM/ABI and each app's requirements.
- Rooted NetHunter Lite: some additional capabilities, but not every
  kernel-dependent feature.
- NetHunter with supported custom kernel: full-feature candidate; availability
  still depends on device/kernel/chipset/external hardware.
- KeX is an Android client for a Kali desktop session; it is not a guarantee
  of GPU, root, or RF hardware support.
- A package minSdkVersion <= Android API 33 only proves minimum SDK
  compatibility, not actual installation or runtime functionality.

Official guides:
https://www.kali.org/docs/nethunter/
https://www.kali.org/docs/nethunter/nethunter-rootless/

## Acceptance gates

1. Run Python unit tests:
   python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v
2. Confirm /api/selma0/tools/v1 exposes the three named descriptors, with
   the correct risk classes.
3. Confirm unapproved catalog_sync is rejected and audits its denial.
4. Confirm an approved sync reaches only the fixed HTTPS official host.
5. Compare cached app count and timestamps with the official Store (reported
   39 apps on 2026-10-28); changes in counts do not imply tampering.
6. Confirm offline catalog reads and failed network sync preserve prior cache.
7. Perform a separate stock Android 13+ device test before declaring support.
8. Do not merge as device-ready until actual tests and audit-chain evidence.

Current state: source integration proposed; CI, live feed sync, and physical
device validation not yet evidenced by this document.
