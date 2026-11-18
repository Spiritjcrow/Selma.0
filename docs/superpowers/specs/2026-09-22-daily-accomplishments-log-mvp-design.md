# SelmaOS Daily Accomplishments Log MVP Design

Date: 2026-09-22  
Status: proposed implementation slice  
Source design: `SelmaOS Automated Daily Accomplishments Log System(1).json`

## Intent

Build the first durable, evidence-first SelmaOS daily accomplishments log. The
system must distinguish what authoritative records prove from what a person,
tool, or language model merely reports. It is intended for the Architect and
future project operators who need a concise morning record that survives
conversation loss, provider outages, and optimistic status wording.

Success for this slice means a local, standard-library Python command can take
a bounded set of normalized GitHub evidence, verify it deterministically, and
render a reproducible Markdown and canonical JSON draft. Missing or conflicting
evidence must remain visibly unverified. Running the command twice with the
same inputs must produce byte-identical machine output.

## Scope

This is the first vertical slice of the larger multi-provider design. It
implements:

- a strict versioned evidence contract;
- duplicate-key rejecting JSON and NDJSON input;
- deterministic verification of GitHub pull-request, commit, workflow-run,
  workflow-job, test-summary, issue-state, and local-observation evidence;
- explicit `VERIFIED`, `UNVERIFIED`, and `INVALIDATED` results;
- claim-level evidence references and human-readable missing-evidence reasons;
- an America/Chicago reporting window with UTC internal timestamps;
- deterministic JSON and Markdown draft rendering;
- SHA-256 integrity values and previous-log hash chaining;
- a command-line interface that operates without network access;
- fixtures proving the actual PR #18 outcome: the merge is verified, repository
  CI is unverified because each Actions run has zero jobs, and local tests do
  not become repository CI evidence.

This slice does not collect live API data, schedule itself, publish a log,
approve a draft, generate a cryptographic signature, or write to immutable
storage. Those actions require provider credentials, a reviewer identity,
external scheduling, or external infrastructure and therefore remain explicit
handoffs. The output is always `DRAFT`.

## Architecture

The implementation lives in `tools/daily_log_v1/` and uses only Python 3.12
standard-library modules. Its modules have narrow responsibilities:

- `models.py`: immutable evidence, claim, verification, and draft-log types;
- `codec.py`: strict parsing, validation, canonical serialization, and
  SHA-256 helpers;
- `verifier.py`: deterministic claim-specific verification rules;
- `renderer.py`: stable Markdown and JSON draft rendering;
- `cli.py`: command-line argument handling and atomic output-directory writes.

The data flow is:

```text
normalized evidence.ndjson
          |
          v
strict decoder + schema validation
          |
          v
claim verifier -----> invalid/missing references become UNVERIFIED
          |
          v
stable claim ordering
          |
          +----> draft.json
          +----> draft.md
          +----> evidence.ndjson
          +----> manifest.json (status DRAFT)
```

The verifier is the only component allowed to assign a verification state.
The renderer cannot promote, infer, or repair evidence.

## Evidence contract

Every input line is one JSON object with these common fields:

```json
{
  "schema": "selmaos.evidence.v1",
  "evidence_id": "github:workflow-run:35680991511",
  "source": "github",
  "kind": "workflow_run",
  "observed_at": "2026-09-22T02:52:00Z",
  "occurred_at": "2026-09-22T02:51:18Z",
  "repository": "Spiritjcrow/Selma.0",
  "payload": {
    "run_id": 35680991511,
    "head_sha": "9a7d3c02036aadbb7f7cf03a03877987af9dda11",
    "status": "completed",
    "conclusion": "startup_failure",
    "workflow_id": 329988227,
    "workflow_name": "",
    "workflow_path": "BuildFailed"
  },
  "source_payload_sha256": "64 lowercase hex characters"
}
```

The accepted `kind` values for this slice are:

- `commit`
- `pull_request`
- `workflow_run`
- `workflow_jobs`
- `test_summary`
- `issue_state`
- `local_observation`

Unknown kinds, unknown top-level fields, duplicate JSON keys, invalid
timestamps, non-UTC timestamps, malformed hashes, Boolean values where an
integer is expected, and oversized lines fail closed. The per-line maximum is
1 MiB. `source_payload_sha256` is verified against the canonical `payload`
object, which may contain only JSON strings, integers, Booleans, null, arrays,
and objects; floats are rejected to keep canonicalization unambiguous.

Claims are separate from evidence. A claim contains:

```json
{
  "schema": "selmaos.claim.v1",
  "claim_id": "2026-09-22:pr-18-merged",
  "claim_type": "code_change",
  "summary": "PR #18 merged into main",
  "repository": "Spiritjcrow/Selma.0",
  "commit_sha": "9a7d3c02036aadbb7f7cf03a03877987af9dda11",
  "evidence_refs": [
    "github:pr:18",
    "github:commit:9a7d3c02036aadbb7f7cf03a03877987af9dda11"
  ],
  "rollback_ref": "revert:9a7d3c02036aadbb7f7cf03a03877987af9dda11"
}
```

The accepted claim types are `code_change`, `ci_result`,
`test_result`, `blocker_state`, and `local_observation`. Deployment and
rollback claims require deployment-provider evidence and are rejected as
unsupported schema values in this offline MVP.

## Verification policy

The MVP applies these mandatory rules:

### Code change

A `code_change` is verified only when:

- referenced PR evidence says `merged: true`;
- its `merge_commit_sha` exactly matches the claim commit;
- referenced commit evidence identifies the same repository and SHA; and
- the commit evidence says the SHA is reachable from the configured trusted
  branch.

A merged PR can therefore be recorded as a verified code change even when CI
is unavailable. It must not imply that tests passed.

### CI result

A successful `ci_result` is verified only when:

- the workflow run targets the exact claim SHA;
- status is `completed`;
- conclusion is `success`;
- a referenced `workflow_jobs` record contains at least one job; and
- every required job is terminal and successful.

`startup_failure`, an empty workflow name, synthetic `BuildFailed` path,
or zero jobs is unverified. The reason must name the observed condition.

### Test result

A `test_result` additionally requires a machine-readable
`test_summary` tied to the exact workflow run and commit SHA, with a positive
test count and zero failures and errors. Console prose and
`local_observation` never satisfy this rule.

### Blocker state

An issue marked closed proves only the state transition. A claim that a blocker
was cleared also requires linked resolving evidence appropriate to the blocker,
such as successful CI for an Actions blocker. Issue #26 therefore remains
unverified until a real job is created and the selected acceptance run
succeeds.

### Local observation

Local commands may be rendered in the unverified section with their observed
result and provenance. They cannot establish repository CI, deployment,
owned-device, or production claims.

### Invalidated

A claim is `INVALIDATED` when authoritative evidence directly contradicts
it, such as a claimed successful CI result whose terminal conclusion is
`startup_failure` or `failure`. Missing evidence is `UNVERIFIED`, not
`INVALIDATED`.

## Reporting window and ordering

The CLI requires `--date YYYY-MM-DD` and defaults to
`--timezone America/Chicago`. It includes claims whose authoritative
`occurred_at` falls inside that local calendar day. The implementation uses
`zoneinfo.ZoneInfo`, converts boundaries to UTC, and handles daylight-saving
transitions through the IANA time-zone database.

Outputs sort claims by:

1. verification state: verified, unverified, invalidated;
2. authoritative event time;
3. claim ID.

Evidence is sorted by `evidence_id`. No filesystem enumeration order or
dictionary insertion order may affect output.

## Output package

The CLI writes to:

```text
logs/YYYY/MM/DD/
├── draft.md
├── draft.json
├── evidence.ndjson
└── manifest.json
```

`draft.json` contains the report window, generator and verifier versions,
verified/unverified/invalidated claim arrays, integrity references, and
`status: "DRAFT"`.

`manifest.json` contains:

- `schema: "selmaos.daily-log-manifest.v1"`;
- date and timezone;
- SHA-256 for `draft.json`, `draft.md`, and `evidence.ndjson`;
- optional `prev_log_sha256`;
- generator and verifier versions;
- `status: "DRAFT"`;
- `reviewer: null`, `approved_at: null`, and `signature_ref: null`.

The CLI writes all files into a sibling temporary directory, fsyncs them, and
renames the directory only after every artifact is complete. It refuses to
replace an existing day unless `--replace-draft` is supplied, and it always
refuses to replace a manifest whose status is not `DRAFT`. Replaced drafts
are preserved beside the current day as
`DD.superseded.<old-manifest-sha256-prefix>`; replacement never deletes the
prior draft.

## CLI

```bash
python3 -m tools.daily_log_v1.cli build \
  --date 2026-09-22 \
  --timezone America/Chicago \
  --evidence evidence.ndjson \
  --claims claims.ndjson \
  --output-root logs \
  --previous-manifest logs/2026/09/21/manifest.json
```

Exit codes are:

- `0`: draft produced successfully, including when some claims are
  unverified;
- `2`: invalid input, schema failure, duplicate identifier, broken evidence
  reference, or unsafe output target;
- `3`: existing output cannot be replaced;
- `4`: previous-manifest hash-chain verification failed.

The CLI prints a one-line summary with verified, unverified, and invalidated
counts. It never prints credential values or raw provider payloads.

## Security and truth boundaries

- No input text can grant tool authority or change verification rules.
- The MVP performs no network calls and reads no ambient credentials.
- Paths are resolved beneath the explicit output root; symlinked output
  components and path traversal are rejected.
- Input size, line size, evidence count, claim count, and rendered output size
  are bounded.
- Raw provider comments and CI logs are outside this slice.
- Unknown schema versions fail closed.
- The renderer escapes Markdown control characters in untrusted summaries.
- A draft is never called approved, signed, finalized, deployed, or archived.

## Test strategy

Tests use `unittest`, temporary directories, literal JSON fixtures, and the
real codec/verifier/renderer. They cover:

- duplicate JSON keys and unknown fields;
- floats, malformed timestamps, oversized input, and duplicate IDs;
- America/Chicago day boundaries across normal and DST days;
- exact SHA binding for PR, commit, workflow, jobs, and test summary;
- successful merge with failed/absent CI remaining two separate claims;
- `startup_failure` plus zero jobs producing explicit unverified reasons;
- local test observations never satisfying repository CI;
- issue closure without resolving evidence not clearing a blocker;
- deterministic byte-for-byte output under shuffled input;
- previous-log hash-chain acceptance and rejection;
- atomic draft replacement and finalized-log overwrite refusal;
- symlink and traversal rejection;
- Markdown escaping.

The acceptance fixture uses PR #18 merge commit
`9a7d3c02036aadbb7f7cf03a03877987af9dda11`, workflow ID
`329988227`, and zero-job runs `35680991511` and `35762629076`.

## External handoffs

The following integrations are deliberately outside the MVP and each receives
a concrete handoff rather than a fabricated completion claim:

- GitHub Support: repair the repository-level Actions startup/admission state
  and synthetic `BuildFailed` workflow registration;
- GitHub App administrator: create a read-only collector installation with
  contents, pull requests, issues, actions, and deployments read access;
- scheduling operator: run the future collector/reconciler after the local
  reporting-day cutoff;
- security/release operator: select reviewer identity, signing mechanism,
  protected log repository, retention, and immutable archive.

No handoff blocks the offline draft builder described here.
