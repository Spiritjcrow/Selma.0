# Selma OSIRIS v0.1
Independent Python 3 standard-library public Earth science metadata sync. No paid API, credentials, camera access, flight commands, or executable remote data. Run in a private working directory; the SQLite database stays local.

    python3 -m unittest discover -s SELMA0_OSIRIS_V1 -p 'test_*.py' -v
    python3 SELMA0_OSIRIS_V1/osiris_sync.py once
    python3 SELMA0_OSIRIS_V1/osiris_sync.py watch --interval 3600
    python3 SELMA0_OSIRIS_V1/osiris_sync.py status

Create OSIRIS.STOP in the working directory to request cooperative stop; remove it to permit a restart. A blocked request is not interrupted immediately. Watch runs only while its process is active. Run a single writer; Android background survival is not verified. No cross-device sync is configured.

NASA EONET: https://eonet.gsfc.nasa.gov/docs/v3
NASA EPIC: https://epic.gsfc.nasa.gov/about/api

The cache retains one normalized metadata snapshot per source; SHA-256 is a content fingerprint, not a signature or tamper-proof ledger. A failed refresh marks health stale and preserves the last good snapshot. Current status does not distinguish source publication latency from refresh latency.

## Candidate gates (not installed)
- GIBS/Worldview: public imagery display, review NASA-1.3 and per-layer data terms.
- GIANT: offline scientific image calibration; verify packaging and license notices.
- SatDump: supported public scientific broadcasts, separate GPL-3.0 distribution review.
- cFS and F Prime: simulation only; no real spacecraft command or control.
- OSIRIS plasma code: scientific simulation, separate compute and license review.
- Osiris AI/MCP/kernel and Osirus DSP: verify identity, license, security and fitness before adoption.
- Selma FDT/agent adapters: local typed read-only interface, policy checks, explicit synchronization authorization and test fixtures before any external relay.
- Camera support: opt-in owned or explicitly authorized devices only; no private camera discovery or individual tracking.

No upstream packages vendored. No live API, full-repository CI, Android runtime or multi-device sync test claimed. Next gates: live API schema validation; strict timeout and retry improvements; concurrent writer and crash tests; read-only Command Center integration; signed handoffs; Android test; pinned dependency and license review. Fixture checks do not establish production readiness.
