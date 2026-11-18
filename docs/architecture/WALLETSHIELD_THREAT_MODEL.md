# WalletShield v0.1: supply-chain integrity triage (2026-10-13)

**Status:** offline Python prototype and tests; not a physical-hardware detector,
not installed as an Android service, and not a production incident-response system.

## Why this exists

Hardware wallets may be modified after manufacture. In October 2026 Ledger
reported an investigation into CryptoBilis-distributed wallets containing an
unauthorized cellular implant that read recovery phrases from a display. A valid
secure-element attestation alone does **not** establish physical integrity.

Read:
- https://www.ledger.com/academy/topics/ledgersolutions/best-practices-to-securely-buy-ledger-signer
- https://donjon.ledger.com/threat-model/device-genuineness/
- https://www.coindesk.com/tech/2026/10/13/ledger-says-spy-chip-inside-cryptobilis-ledger-devices-transmitted-wallet-keys-over-mobile-network

## Run without Android root, ADB, Termux, internet, or a wallet

From the repository root with Python 3.11+:

1. Save the following to a local file named wallet_case.json:

    {
      "case_id": "case_0001",
      "observations": [
        {
          "kind": "supply_chain",
          "result": "fail",
          "method": "documented_receipt"
        },
        {
          "kind": "vendor_attestation",
          "result": "unknown"
        }
      ]
    }

2. Run: python3 -m core.wallet_shield assess wallet_case.json
3. Optional, private hash-linked local log:
   python3 -m core.wallet_shield assess wallet_case.json --audit walletshield-audit.jsonl
4. Verify: python3 -m core.wallet_shield verify walletshield-audit.jsonl
5. To export a report *to a local file only* with owner approval:
   python3 -m core.wallet_shield assess wallet_case.json --export review.json --owner-approved

Run tests: python3 -m unittest tests.test_wallet_shield -v

### Accepted observation types

| kind | method to qualify supporting metadata | How to interpret |
|---|---|---|
| supply_chain | documented_receipt | provenance concern, not evidence of crime |
| vendor_attestation | official_vendor_client | official-client test outcome as reported |
| physical_inspection | qualified_inspector | external inspection metadata only |
| rf_survey | calibrated_external_receiver | externally collected RF finding, baseline to be checked by a human |
| chain_activity | public_chain_review | reported chain anomaly, not evidence of implant |

Each observation takes a result: pass, fail, or unknown. Optional evidence_sha256
must be the lowercase SHA-256 digest of an *external* evidence artifact. The
engine does **not** authenticate the artifact, inspect its contents, or check
whether an inspector is qualified. The qualifier only controls **urgency of
human review**, never a finding of compromise. Physical disassembly risks
destroying evidence and warranty; use a qualified lab.

**Do not provide recovery phrases, PINs, private keys, wallet addresses,
serial numbers, names, messages, photos, or raw RF data to this module.**
Unknown/free-text fields are rejected rather than stored.

## Sol division of responsibilities

- **Sol Blue**: intake receipts and owner-authorized evidence hashes, ask
  users to run official vendor genuineness checks, and assign review status.
- **Sol Red**: controlled validation on *owned lab reference hardware only*.
  Independent physical imagery and RF measurements must be made using
  calibrated external equipment and a known-good baseline (not yet enforced by software). No cloning,
  implants, traffic interception, or unauthorized RF transmitting.
- **Sol UltraViolet**: check provenance, audit-chain validation, second-person
  review, explicit permission and legal handling. Owner must approve each
  outbound report; no automatic accusation, attribution, account action, or
  law-enforcement notification.

## Present limits

- This is **passive triage**, not direct USB, BLE, LTE, OLED, or RF scanning.
- Ordinary Android phones cannot reliably detect an independent hidden modem.
  No suspicious radio event is by itself proof of a hardware implant.
- Local SHA-256 chains detect many edits but not rehashing or wholesale
  deletion by a malicious local operator. External signed checkpoints and
  encrypted evidence vaults are a separate production milestone.
- App permission integration, user-visible review, vendor interfaces, calibrated
  adapters, encrypted storage, Android packaging, and adversarial trials are
  **not implemented**.
- No network calls or automatic reports; status remains unverified until an
  independent authorized investigator confirms the case.

## Community-wide protection policy (owner directive, 2026-10-13)

**Purpose:** continuous availability of defensive protection to all Selma users,
not centralized observation of their devices, chats, wallets or identities.
"Overwatch" means distributing reviewed public threat indicators and running
protective checks on each participating device, not indiscriminate monitoring.

- Every participating member can receive vetted, case-free hardware-wallet
  threat advisories; no individual reports are embedded in notifications.
- Private device analysis is local-first. User consent is required before
  optional sensors, individual telemetry, uploads, support access or sharing.
  Declining telemetry must not disable local protective advisories.
- **Default telemetry is OFF** as are remote investigator access, member tracking,
  message interception, secret collection, and automatic authority reports.
- Member-to-member surveillance is never a supported operation.
- The incident/recovery UI should offer transparent "What is being checked?",
  "What leaves this device?", "Stop monitoring", "Revoke access",
  "Export my evidence" and "Delete locally retained case data" controls,
  consistent with preservation obligations and verified legal holds.
- Community trend reports require separately engineered opt-in, privacy-
  preserving aggregation and robust anti-reidentification controls.
  This is a **future feature** and not a deployed capability. Never harvest
  per-user communications, RF records, wallet secrets or device identities.

### Scoped escalation

**Sol Blue / community:** publish reviewed public defensive advisories and
process owner-entered local risk indicators without central collection.

**Specialists on demand:** a verified professional needs explicit victim
permission, verified case assignment, time-limited purpose-specific access,
and independent action-level authorization. A claimed specialty/login is
insufficient. Use approved, non-destructive or owner-authorized methods.

**Legal authorities:** require BOTH a verified case-specific judicial
authorization/warrant and the victim's explicit, scoped consent as Selma
policy for *voluntary* disclosure. Verify authority identity, order
authenticity, scope/data categories, independent reviewer, expiry and notice
restrictions. Never give authorities global/backdoor access. Requests beyond
this voluntary release policy require independent qualified legal review
under applicable law: product policy does not override legal obligations.

**Victim recovery:** non-custodial safety guidance, official vendor contacts,
safe movement of remaining funds to a new hardware wallet/new recovery phrase
and integrity-protected evidence packaging. Specialists and authorities do
not need and must never request seed phrases or private keys. Selma does not
move funds or take custody of assets.

### Code boundary, current truth

core/wallet_shield_access.py provides a default-deny policy preflight and
explicit community privacy defaults. check_access denies unknown verifiers,
missing or unverified attestations, expired sessions and cross-role calls.
Specialist reviews require verified professional role, assignment and victim
consent. Legal evidence requests require authority role, court order, judge
authorization, victim consent, case scope, and independent reviewer.
Public advisories cannot identify individual cases.

**Not implemented:** production signed-credential verification, real warrant
authentication, legal analysis, actual case access, revocation service,
trusted clock, monitoring UI, privacy-preserving community aggregation,
public-advisory publishing, audit server, identity validation, court-compliant
retention or secure evidence delivery. A positive preflight outcome never
releases data. Its test-time verifier is NOT a substitute for a trusted
production verifier. Future effects must route through Selma's existing
scoped permission controller, with checks repeated at execution time.

## Incident response

If a wallet may have displayed its recovery phrase to an implant, stop using
that device. Obtain a fresh hardware wallet from a verified channel and generate
a **new** recovery phrase on it. Arrange transfer of remaining assets to
addresses controlled by the fresh phrase using the vendor's current official
guidance and careful on-device address verification. Do not merely import the
suspected compromised phrase onto another wallet. Preserve purchase records
and contact the vendor and appropriate authorities after gathering evidence.

Do not name or confront alleged culprits based on radio anomalies or reseller
information alone.
