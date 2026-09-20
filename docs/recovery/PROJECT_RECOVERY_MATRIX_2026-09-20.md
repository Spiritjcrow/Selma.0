# Project Recovery Matrix — 2026-09-20

This file records verified blocker state only. It does not convert local tests, chat claims, or planned work into repository CI/device evidence.

## 1. SelmaOS Gate 1

- Controlling issue: #15
- Implementation PR: #18
- Current PR head observed: `772c9359c7ba13669f27d847796e9d2525b83ab4`
- GitHub Actions run observed: `33913982025`
- Result: `startup_failure`, workflow id `329988227`, zero jobs created.
- Re-run attempt through the GitHub API: rejected with HTTP 403, “This workflow run cannot be retried.”
- Repository-side isolation already showed the failure occurs before Selma build/test jobs are admitted.

**Native repair path:** repair GitHub Actions repository/account admission state first, then rerun the unchanged workflows. Do not churn Selma application code for this pre-job failure.

## 2. Selma dependency chain

Gate 1 remains the central merge gate.

- #16 avatar work depends on Gate 1 contracts.
- PR #21 and PR #22 are stacked behind Gate 1 and cannot obtain a clean merge/CI path until #18 is resolved or an owner-approved CI exception is documented.
- #1 / PR #12 offline llama.cpp still requires real Android/Termux + local GGUF evidence.
- #4 / PR #13 native Android shell still requires CI artifact evidence and owned-device install/overlay/service validation.
- PR #6 local RAG is valuable but stale and must be ported onto current main rather than merged as-is.
- PR #8 Forge/Selmatizer is valuable but stale and must be ported through the current command/permission/audit plane.

## 3. FDT / WingDingynouse

- Current implementation PR: #29
- Current PR head observed: `8355bc507da9f1cf375c6908cdc7ba51b9103c2a`
- GitHub Actions run observed: `34365961150`
- Result: `startup_failure`, workflow id `329988227`, zero jobs created.
- Re-run attempt through the GitHub API: rejected with HTTP 403, “This workflow run cannot be retried.”
- PR-local test/demo claims remain local evidence until repository CI can actually start.

**Native repair path:** use the same Actions admission repair as Gate 1, then rerun FDT Gate unchanged. Keep older v0.7.1 lease/telemetry failures separate unless reproduced on the current v0.7 line.

## 4. New recovery capability

Branch `selma-project-recovery-inspector-v1` adds one shared evidence-first recovery engine plus project manifests.

Registered tools:

- `recovery.inspect_project` — read-only project/source/chat-export inspection.
- `recovery.inspect_workspace` — read-only multi-project inspection.
- `recovery.write_report` — permissioned report write.

The engine distinguishes CI admission, failing tests, policy/permission blocks, stale branches, dependency/environment drift, missing implementation, missing acceptance evidence, external gates, and vague hold markers.

It does not claim automatic access to the ChatGPT account. Full-chat analysis requires a user-authorized export such as `conversations.json`, or another explicitly connected source.

## 5. Project manifests included

- Selma.0 / SelmaOS
- Flipp’n Da Table! / WingDingynouse / FDT Gate
- Vedic / Natal Cosmos Explorer
- VΩX Forensic Acoustic Studio / AudioMatrix
- Android Rescue Toolbox
- Cobra DVR / Cobra Companion
- CrowIDE AI-App Builder

The manifests hold project-specific keywords and known verified external gates while keeping the diagnosis engine shared.
