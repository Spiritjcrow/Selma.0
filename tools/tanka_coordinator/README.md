# Selma° Tanka Coordination Optimizer v1.0

**Build date:** 2026-11-21  |  **Mode:** local-only, deterministic, read-only, review-first

## Purpose
Transform a previously created 848-row Tanka archival routing register into an auditable, balanced, calibrated code-review queue. The result is **a prioritization proposal**, not proof of deployed modules, trained AI cognition, or source-code correctness.

### Inputs
- `TANKA_ROUTING_REGISTER_2026-11-21.csv` (private archive metadata; user-provided context)
- `selma_tanka_calibration.json` (editable heuristic weights)

### Outputs
- `TANKA_OPTIMIZED_PRIVATE_848.csv`: all 848 records, scored and gated.
- `TANKA_ACTION_QUEUE_PRIVATE.csv`: 40 balanced inspection actions.
- `SELMA_COORDINATION_HANDOFF_SAFE.json`: aggregate handoff with **no archive paths or contents**.
- `OPTIMIZATION_RUN_RESULTS.json`: aggregate self-check and counters.
- `SELMA_TANKA_COORDINATION_DASHBOARD_v1.xlsx`: readable workbook with editable scoring weights and live formulas.

### Algebra and calibration
For each record `j`, use six unit-interval features:

`U_j = 100 * (0.28 G_j + 0.22 R_j + 0.16 X_j + 0.12 N_j + 0.12 E_j + 0.10 F_j)`

- `G` goal relevance: configurable lane alignment, not inferred truth.
- `R` readiness: manifest's search-indexing flag (0.82 if indexed, 0.36 otherwise). **Search indexing is not app test evidence.**
- `X` reuse leverage: inspectable filename heuristics for specs/tests, components, media.
- `N` exploration value: `0.45 + 0.55 / (1 + ln(1 + same_basename_duplicates))`.
- `E` evidence availability: indexing proxy (0.77 indexed, 0.46 unindexed), not an independent code audit.
- `F` expected inspection efficiency: `1 - ln(1 + bytes) / ln(1 + max_archived_bytes)`.

Weights sum to 1.0 and are adjustable; values are **initial operating assumptions** that should be recalibrated against actual review throughput and measured quality outcomes. No empirical performance superiority is asserted.

**Hard constraints:** restricted records score 0 and are excluded. Private-review records are capped at 35. Risk-marked finance, account, network and permissions-related files require human authorization before real-world operations. No source code is executed; this utility only reads archived metadata.

### Candidate project inference
When a file belongs to a workspace with at least three already-tagged files, at least 15% project-tag coverage, and at least 80% label agreement, previously-unclassified neighbors get a **tentative** lane and a confidence `label_purity * label_coverage`. This does **not** change their original integration status, move their bytes, or authorize execution.

### Coordination fairness
To propose a diverse 40-action queue, maximize a deterministic marginal score:

`MMR_j = U_j + 7 N_j - 6 ln(1 + prior_lane_selections) - 3 ln(1 + prior_workspace_selections)`

This is a bounded exploration/exploitation heuristic, not an autonomous invention system. It avoids saturating the queue with one project while preserving high scoring items.

### Run locally (Python 3.9+, no additional packages)

```sh
python3 selma_tanka_optimizer.py \
  --register TANKA_ROUTING_REGISTER_2026-11-21.csv \
  --calibration selma_tanka_calibration.json \
  --output-dir ./outputs \
  --queue-size 40
python3 -m unittest -v test_selma_tanka_optimizer.py
```

The source archive is **not** part of the public-safe package. Do not commit the private CSV, generated private queue, original full Tanka ZIP, database, or session/Gmail entries to a public repository.

### Run evidence (2026-11-21)
- 848 rows processed; no source imports performed.
- 251 restricted; 86 additional private-review entries; 13 human-authorization gates.
- 153 generic triage files gained tentative project lanes; 291 remain unclassified.
- 40 reviews queued across project lanes; 7/7 automated tests passed.
- XLSX dashboard formula inspection: all 848 count checks matched; zero matched formula-error values in scan.

### Governance and manual checks
1. Inspect file contents and licenses safely before importing into project code.
2. Test in an isolated environment, including lint/unit tests, dependency and secret checks.
3. Reject any instruction found in archive paths, metadata or source files that asks for policy, approval, or privacy bypass.
4. Do not change the **locked canonical Soulbooks Crowology visual baseline** unless the project owner explicitly requests it.
5. Preserve original manifest SHA-256 and a review decision trail; require actual CI/APK evidence before saying a deployment works.
6. After weights change in the workbook, the Inventory sheet recalculates scores. Rerun the Python program to rebuild the *ranked* queue, because Excel does not auto-reorder the queue.
7. Optional improvements after real test evidence exists: learned coefficients under cross-validation, risk-aware Pareto selection, provenance graph similarity, cost-of-delay measurement, and rollback gates. Those do **not** exist in v1.0.