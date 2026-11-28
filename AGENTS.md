# Selma° coding-agent operating instructions

Before modifying Selma° or reporting completion:

1. Read [the master execution ledger](docs/architecture/SELMA_MASTER_EXECUTION_LEDGER.md).
2. Inspect `main`, relevant PRs, issues, branches and current commit SHAs.
3. Keep verified results separate from code-only prototypes, draft PRs,
   failed or absent CI jobs, and physical-device results.
4. Use feature branches and reviewable changes for runtime code. Preserve the
   existing command-router approval, replay/idempotency and audit controls.
5. Do not silently change model/provider, session/thread identity, empathy
   enforcement, capability availability or platform targets.
6. Text and voice are modalities of the **same logical Selma° assistant**.
   A model process restart is not an identity reset. No memory/identity erase
   may be inferred from a mode switch.
7. The Reciprocal Empathy Principle (`SELMA-COG-RECIPROCITY-001`) is a
   mandatory chat policy; complete cross-agent enforcement only when verified.
8. After changes, add verification commands, results, file paths, head SHA,
   rollback and remaining blockers to the ledger or referenced issue/PR.
9. Controlled activation target is provisionally **2026-12-19**, contingent
   on passing safety, CI, integration and owner-device gates. Do not claim
   a deployment or treat that date as automatic authorization.
10. Do not create additional competing project truth files: link the
    canonical ledger instead.

A chat, memory summary, draft specification, or agent declaration does not
prove code execution or user-device integration.
