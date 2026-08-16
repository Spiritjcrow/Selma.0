# Selma Data Compiler v1

Local-first compiler/indexer for Selma project data. It scans one or more Selma roots, classifies artifacts into canonical domains, records provenance, detects duplicates/conflicts, builds a dependency map, and emits a needs report without destructively rewriting source files.

## Rules

- Source files are read-only.
- Canonical output goes to `.selma/compiler/` by default.
- Exact duplicates collapse by SHA-256.
- Potential conflicts are retained; contradictory data is never silently overwritten.
- Every record carries source path, hash, evidence state, confidence, mapping reason, and timestamps.
- `planned`, `placeholder-or-partial`, `source-present`, and `generated` remain distinct states.
- Deterministic path/file-role mapping wins over heuristic keyword inference.
- No network or cloud dependency is required.

## Canonical domains

`core`, `agents`, `memory`, `voice`, `avatar`, `devices`, `network`, `adapters`, `automations`, `runtime`, `experiments`, `local-sandbox`, `safety`, `config`, `tests`, `docs`, `build`, `ui`, `unknown`.

## Usage

```bash
python -m pip install -e tools/selma-data-compiler
selma-compile compile .
selma-compile compile ~/Selma.0 ~/SelmaRF
selma-compile explain .
selma-compile needs .
```

Outputs:

- `.selma/compiler/manifest.json`
- `.selma/compiler/dependency_map.json`
- `.selma/compiler/conflicts.json`
- `.selma/compiler/needs.json`
- `.selma/compiler/catalog.sqlite3`

## Evidence ranking

1. explicit `selma:canonical` declarations
2. current configuration declarations
3. runtime/database evidence
4. source code
5. manifests/UI resources
6. documentation and plans
7. inferred/generated metadata

Freshness is only a tie-breaker within the same authority class.
