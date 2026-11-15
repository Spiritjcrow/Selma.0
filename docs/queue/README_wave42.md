# Selma° generic queue accelerator | wave 42 (review-only)

This configuration **plans, but never executes**, bounded microsteps across the existing private `Spiritjcrow/Selma.0` issue/PR queue. It is not a new schedule, privileged worker, or always-on process.

## Evidence and source of truth
- Canonical queue: [#88](https://github.com/Spiritjcrow/Selma.0/issues/88).
- Program tracker and dependencies: [#17](https://github.com/Spiritjcrow/Selma.0/issues/17).
- Existing Universal Fixer inventory: [draft PR #104](https://github.com/Spiritjcrow/Selma.0/pull/104), which reports 119 tracking objects across 13 repositories (79 PRs and 40 issues). This manifest contains **42 currently open, real, linked Selma.0 issue/PR objects**, sampled separately. The two counts are not additive.
- Planning states are conservative triage classifications and must be refreshed from issue/PR source before action; 42 objects are not 42 independent defects or worker instances.

## Run (Python 3.10+, stdlib, offline, no credentials)
```bash
python3 tools/queue_planner.py docs/queue/selma_wave42_seed.json --batch 0 --limit 7
python3 tools/queue_planner.py docs/queue/selma_wave42_seed.json --batch 1 --limit 7
python3 -m unittest discover -s tests -p 'test_queue_planner.py' -v
```

There are 42 source objects, including one existing CI blocker (#26) and one exclusively reserved security issue (#43); therefore **40 are initially eligible for read-only triage**, not write permission or automated completion. The standalone planner emits a deterministic SHA-256 digest over its selected plan and an explicit `actually_executed: 0`. It never imports automation runners, writes to GitHub, calls a model, issues network requests, or processes credentials.

## General-purpose configuration
- **Throughput cap:** up to 7 small read-only candidate reviews per existing activation; NEVER seven-times scheduler frequency.
- **Safety:** one authoritative coordinator owns cross-lane claims; no candidate in this file is auto-claimed. Check fresh head SHA, owner, dependencies, current CI result, and prior checkpoints before any write.
- **Collision handling:** never schedule two same-resource writes. Use `conflict_group` (and newest issue/PR relations) when transforming a dry-run plan into a human-reviewed work list.
- **Blockers:** `BLOCKED`, `RESERVED_SOL_RED` and `COMPLETE` are excluded. #43 stays exclusive to Sol Red; #26 remains blocked until a genuinely admitted runner job is observed. Do not blindly retry.
- **Approval:** `approval_to_mutate` is always false. The script *rejects* any manifest entry trying to enable mutation. Actual source changes require an independently scoped authorized tool call and branch/review gates.
- **Evidence:** append one meaningful changed checkpoint to #88 with original SHA, actual tests, artifact link and next action. Do not mark `VERIFIED` on read-only planning.
- **Cadence:** existing ChatGPT Operations Coordinator is hourly; this file does not create a task, daemon, webhook, CI trigger, paid service, deploy or publication.

## Task selection and continuation
Choose a batch index `--batch N`. Each output is a list of **candidate review instructions**, not a command to invoke them. Read the referenced source immediately before using it; the seed was captured 2026-11-15 and may be stale. Prefer a completed independent RED→GREEN repair from the existing Universal Fixer (#104) over another redundant prototype. Check source-level tests, then runner and Android device acceptance separately.

## Known limits
- Source repo main and all existing PRs remain unchanged by this branch-only configuration.
- No script run or CI result is claimed by the presence of source files alone; inspect actual test logs.
- Related PR #114 HyperCore UI and #108 Codemagic SDK correction are **draft**; artifact download/checksum and owned Android 11+ install remain open.
- Some seed entries are issue/PR pairs or overlapping workstreams. They are **tracking objects**, not automatically independent execution units.
