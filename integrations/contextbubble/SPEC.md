# Selma ContextBubble: implementation contract v0.1

Status: proposed specification, not implemented or deployed.

## UI
- Small floating launcher inside the SelmaOS Android app; tap to expand to a larger chat/activity panel.
- Aggregated streams grouped by source, project, time and verification status.
- Expandable evidence cards with source permalink, timestamp, claim, confidence and explicit verification state.
- Search, filter and collapse; accessible touch targets and Android 11+ compatibility.
- No attempt to modify ChatGPT's proprietary application UI.

## Data
- Provider adapters for authorized GitHub, Drive and other explicitly connected sources.
- Read-only ingestion by default, per-provider opt-in and scoped credentials.
- Deduplicate by provider, stable external ID and content hash.
- Persist normalized event records in local SQLite with schema migrations.
- Never treat generated claims as source-verified evidence.

## Safety and audit
- No silent cross-service forwarding; permission check for every export.
- Secrets remain outside repository and logs.
- Manual override can reject suggestions, never bypass test or evidence gates.
- Kill switch disables polling, network adapters and UI overlay.
- Offline-first cache with bounded retention and redaction for sensitive material.

## Acceptance checks
1. UI can open/close and resize without obstructing Android navigation.
2. Identical events from two syncs appear once.
3. Every displayed fact has a source reference and retrieval timestamp.
4. Offline mode displays cached records with stale indicators.
5. Kill switch stops polling; audit events remain available.
6. Connector failure never crashes the host agent.
7. Unit, integration, Android device and security checks pass before verified label.

## Verification status
No runtime, UI build, device test or connector execution evidence attached.
