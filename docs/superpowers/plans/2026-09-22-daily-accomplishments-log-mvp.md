# SelmaOS Daily Accomplishments Log MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline deterministic draft generator that keeps verified GitHub accomplishments separate from unverified or contradicted claims.

**Architecture:** A standard-library Python package reads strict evidence and claim NDJSON, indexes evidence by immutable ID, applies claim-specific fail-closed rules, then atomically renders canonical JSON, Markdown, normalized evidence, and a draft manifest. Provider collection, scheduling, approval, signing, and immutable archival stay behind explicit external handoffs.

**Tech Stack:** Python 3.12 standard library, `dataclasses`, `enum.StrEnum`, `json`, `hashlib`, `zoneinfo`, `argparse`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-22-daily-accomplishments-log-mvp-design.md`

## Global Constraints

- Use Python 3.12 standard-library modules only.
- The runtime performs no network calls and reads no ambient credentials.
- Every output remains `DRAFT`; this slice cannot claim approval, signing, publication, deployment, or archival.
- JSON decoding rejects duplicate keys, floats, unknown fields, invalid UTC timestamps, and unsupported schema versions.
- Verification state is assigned only by the verifier; rendering cannot promote evidence.
- Missing mandatory evidence is `UNVERIFIED`; authoritative contradiction is `INVALIDATED`.
- Repository CI requires an exact SHA, a completed successful workflow run, and at least one successful terminal job.
- Machine-readable test evidence is required for a verified test claim.
- Output is deterministic under reordered inputs.
- Writes are atomic, bounded beneath the explicit output root, and cannot replace a non-draft manifest.

## Review Focus

- Truthy values masquerading as integers or Booleans must fail schema validation; Task 1 pins exact type checks.
- Duplicate or conflicting evidence IDs must fail rather than let input order choose the winner; Task 1 tests both cases.
- A merged PR with `startup_failure` CI must yield one verified merge claim and a separate unverified/invalidated CI claim; Task 2 uses the PR #18 fixture.
- Day-window boundaries must remain correct across America/Chicago daylight-saving transitions; Task 3 tests 23-hour and 25-hour dates.
- Output replacement through symlinks, traversal, or an existing non-draft manifest must be rejected; Task 4 tests each path.

---

### Task 1: Strict evidence and claim contracts

**Files:**
- Create: `tools/daily_log_v1/__init__.py`
- Create: `tools/daily_log_v1/models.py`
- Create: `tools/daily_log_v1/codec.py`
- Create: `tests/test_daily_log_v1_codec.py`

**Interfaces:**
- Consumes: UTF-8 JSON/NDJSON bytes supplied by the caller.
- Produces: `EvidenceRecord.from_mapping(value)`, `Claim.from_mapping(value)`, `load_evidence(path)`, `load_claims(path)`, `canonical_json_bytes(value)`, and `sha256_hex(data)`.

- [ ] **Step 1: Write contract tests that reject ambiguous input**

```python
class StrictCodecTests(unittest.TestCase):
    def test_duplicate_json_key_is_rejected(self):
        path = self.write('{"schema":"selmaos.evidence.v1","schema":"other"}\n')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            load_evidence(path)

    def test_boolean_is_not_an_integer(self):
        value = valid_evidence()
        value["payload"] = {"run_id": True}
        value["source_payload_sha256"] = sha256_hex(
            canonical_json_bytes(value["payload"])
        )
        with self.assertRaisesRegex(ValueError, "run_id must be an integer"):
            EvidenceRecord.from_mapping(value)

    def test_float_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "floats are not supported"):
            canonical_json_bytes({"duration": 1.25})

    def test_duplicate_evidence_id_is_rejected(self):
        record = valid_evidence()
        path = self.write(
            json.dumps(record, separators=(",", ":")) + "\n"
            + json.dumps(record, separators=(",", ":")) + "\n"
        )
        with self.assertRaisesRegex(ValueError, "duplicate evidence_id"):
            load_evidence(path)

    def test_unknown_top_level_field_is_rejected(self):
        value = valid_evidence()
        value["surprise"] = "ignored only by unsafe decoders"
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            EvidenceRecord.from_mapping(value)
```

- [ ] **Step 2: Run the codec tests and verify the red state**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_codec -v
```

Expected: import failure because `tools.daily_log_v1` does not exist.

- [ ] **Step 3: Implement immutable models with exact schemas**

```python
class EvidenceKind(StrEnum):
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    WORKFLOW_RUN = "workflow_run"
    WORKFLOW_JOBS = "workflow_jobs"
    TEST_SUMMARY = "test_summary"
    ISSUE_STATE = "issue_state"
    LOCAL_OBSERVATION = "local_observation"


class ClaimType(StrEnum):
    CODE_CHANGE = "code_change"
    CI_RESULT = "ci_result"
    TEST_RESULT = "test_result"
    BLOCKER_STATE = "blocker_state"
    LOCAL_OBSERVATION = "local_observation"


class VerificationState(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class EvidenceRecord:
    schema: str
    evidence_id: str
    source: str
    kind: EvidenceKind
    observed_at: datetime
    occurred_at: datetime
    repository: str
    payload: Mapping[str, JsonValue]
    source_payload_sha256: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "EvidenceRecord":
        require_exact_fields(value, EVIDENCE_FIELDS, "evidence")
        if value["schema"] != "selmaos.evidence.v1":
            raise ValueError("unsupported evidence schema")
        payload = require_json_object(value["payload"], "payload")
        digest = require_sha256(value["source_payload_sha256"], "source_payload_sha256")
        if sha256_hex(canonical_json_bytes(payload)) != digest:
            raise ValueError("source_payload_sha256 does not match canonical payload")
        return cls(
            schema="selmaos.evidence.v1",
            evidence_id=require_text(value["evidence_id"], "evidence_id"),
            source=require_text(value["source"], "source"),
            kind=EvidenceKind(value["kind"]),
            observed_at=require_utc_datetime(value["observed_at"], "observed_at"),
            occurred_at=require_utc_datetime(value["occurred_at"], "occurred_at"),
            repository=require_repository(value["repository"]),
            payload=MappingProxyType(payload),
            source_payload_sha256=digest,
        )
```

`Claim.from_mapping` follows the same exact-field pattern and validates a
40-character lowercase commit SHA when `commit_sha` is present. Helper
functions reject `bool` before accepting `int`, reject strings containing
ASCII control characters, and require UTC `Z` timestamps.

- [ ] **Step 4: Implement strict NDJSON and canonical JSON**

```python
def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_json_bytes(value: JsonValue) -> bytes:
    reject_floats_and_non_json(value, path="$")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_evidence(path: Path) -> tuple[EvidenceRecord, ...]:
    records = tuple(
        EvidenceRecord.from_mapping(item)
        for item in load_ndjson(path, max_lines=10_000, max_line_bytes=1_048_576)
    )
    reject_duplicate_ids(records, attribute="evidence_id")
    return records
```

Decode each physical line independently with
`json.loads(..., object_pairs_hook=_unique_object, parse_float=reject_float)`.
Reject blank lines, invalid UTF-8, more than 10,000 records, and trailing
non-whitespace data within a line.

- [ ] **Step 5: Run Task 1 tests**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_codec -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add tools/daily_log_v1/__init__.py tools/daily_log_v1/models.py \
  tools/daily_log_v1/codec.py tests/test_daily_log_v1_codec.py
git commit -m "Add strict daily-log evidence contracts"
```

### Task 2: Fail-closed verification engine

**Files:**
- Create: `tools/daily_log_v1/verifier.py`
- Create: `tests/fixtures/daily_log_v1/pr18-evidence.ndjson`
- Create: `tests/fixtures/daily_log_v1/pr18-claims.ndjson`
- Create: `tests/test_daily_log_v1_verifier.py`

**Interfaces:**
- Consumes: `Sequence[EvidenceRecord]` and one `Claim`.
- Produces: `EvidenceIndex(records)` and
  `verify_claim(claim, index) -> VerificationResult`.

- [ ] **Step 1: Write tests for exact linkage and PR #18 separation**

```python
class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.evidence = load_evidence(FIXTURES / "pr18-evidence.ndjson")
        self.claims = load_claims(FIXTURES / "pr18-claims.ndjson")
        self.index = EvidenceIndex(self.evidence)

    def result(self, claim_id):
        claim = next(item for item in self.claims if item.claim_id == claim_id)
        return verify_claim(claim, self.index)

    def test_merged_pr_is_verified_without_implying_ci_success(self):
        result = self.result("2026-09-22:pr-18-merged")
        self.assertEqual(VerificationState.VERIFIED, result.state)
        self.assertEqual((), result.reasons)

    def test_startup_failure_with_zero_jobs_invalidates_success_claim(self):
        result = self.result("2026-09-22:pr-18-ci-success")
        self.assertEqual(VerificationState.INVALIDATED, result.state)
        self.assertIn("conclusion=startup_failure", result.reasons)
        self.assertIn("workflow created zero jobs", result.reasons)

    def test_local_observation_cannot_satisfy_repository_ci(self):
        ci_claim = replace(
            claim_by_id(self.claims, "2026-09-22:pr-18-ci-success"),
            evidence_refs=("local:tests:pr18",),
        )
        result = verify_claim(ci_claim, self.index)
        self.assertEqual(VerificationState.UNVERIFIED, result.state)
        self.assertIn("workflow_run evidence is required", result.reasons)

    def test_closed_actions_issue_does_not_clear_without_successful_job(self):
        result = self.result("2026-09-22:issue-26-cleared")
        self.assertEqual(VerificationState.UNVERIFIED, result.state)
        self.assertIn("resolving CI evidence is missing", result.reasons)
```

- [ ] **Step 2: Add literal PR #18 evidence fixtures**

The fixture contains:

- PR #18 merged at `9a7d3c02036aadbb7f7cf03a03877987af9dda11`;
- a commit record marking that SHA reachable from `main`;
- Actions runs `35680991511` and `35762629076`, both completed with
  `startup_failure`, empty name, path `BuildFailed`, workflow ID
  `329988227`;
- one `workflow_jobs` record per run with `jobs: []`;
- a local observation recording 71 + 23 passing tests without labeling it
  repository CI;
- issue #26 remaining open.

Every fixture digest is the SHA-256 of the literal canonical payload.

- [ ] **Step 3: Run verifier tests and verify the red state**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_verifier -v
```

Expected: import failure because `verifier.py` does not exist.

- [ ] **Step 4: Implement the evidence index and dispatcher**

```python
@dataclass(frozen=True)
class VerificationResult:
    claim: Claim
    state: VerificationState
    reasons: tuple[str, ...]
    occurred_at: datetime


class EvidenceIndex:
    def __init__(self, records: Sequence[EvidenceRecord]):
        self._by_id = {record.evidence_id: record for record in records}
        if len(self._by_id) != len(records):
            raise ValueError("duplicate evidence_id")

    def referenced(self, claim: Claim) -> tuple[EvidenceRecord, ...]:
        missing = [ref for ref in claim.evidence_refs if ref not in self._by_id]
        if missing:
            raise MissingEvidence(tuple(sorted(missing)))
        return tuple(self._by_id[ref] for ref in claim.evidence_refs)


def verify_claim(claim: Claim, index: EvidenceIndex) -> VerificationResult:
    try:
        records = index.referenced(claim)
    except MissingEvidence as exc:
        return unresolved(claim, *(f"missing evidence: {ref}" for ref in exc.refs))
    handler = VERIFY_HANDLERS[claim.claim_type]
    return handler(claim, records)
```

- [ ] **Step 5: Implement claim-specific rules**

```python
def verify_ci_result(
    claim: Claim, records: Sequence[EvidenceRecord]
) -> VerificationResult:
    runs = select_kind(records, EvidenceKind.WORKFLOW_RUN)
    jobs_records = select_kind(records, EvidenceKind.WORKFLOW_JOBS)
    if not runs:
        return unresolved(claim, "workflow_run evidence is required")
    run = require_single(runs, "workflow_run")
    reasons: list[str] = []
    contradicted = False
    if run.payload["head_sha"] != claim.commit_sha:
        reasons.append("workflow commit does not match claim commit")
    if run.payload["status"] != "completed":
        reasons.append(f"workflow is not terminal: status={run.payload['status']}")
    if run.payload["conclusion"] != "success":
        reasons.append(f"conclusion={run.payload['conclusion']}")
        contradicted = run.payload["status"] == "completed"
    jobs = jobs_for_run(jobs_records, run.payload["run_id"])
    if not jobs:
        reasons.append("workflow created zero jobs")
    elif any(job["status"] != "completed" or job["conclusion"] != "success" for job in jobs):
        reasons.append("one or more required jobs did not succeed")
        contradicted = True
    return result_for(claim, reasons, contradicted=contradicted, records=records)
```

`verify_code_change` requires one merged PR and one reachable commit with
exact repository/SHA linkage. `verify_test_result` first applies CI rules and
then requires a positive `test_summary.tests` integer with zero failures and
errors. `verify_blocker_state` does not accept issue closure alone.
`verify_local_observation` always returns `UNVERIFIED` with the reason
`local observation is not authoritative repository evidence`.

- [ ] **Step 6: Run Task 2 tests**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_verifier -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add tools/daily_log_v1/verifier.py tests/fixtures/daily_log_v1 \
  tests/test_daily_log_v1_verifier.py
git commit -m "Verify daily accomplishments from exact evidence"
```

### Task 3: Reporting window, deterministic renderer, and integrity chain

**Files:**
- Create: `tools/daily_log_v1/renderer.py`
- Create: `tests/test_daily_log_v1_renderer.py`

**Interfaces:**
- Consumes: report date, IANA time-zone name, evidence records, claims,
  optional previous manifest.
- Produces:
  `build_draft(...) -> DraftPackage`,
  `render_markdown(package) -> bytes`,
  `render_json(package) -> bytes`, and
  `build_manifest(package, artifact_bytes, previous_manifest) -> bytes`.

- [ ] **Step 1: Write reporting-window and determinism tests**

```python
class RendererTests(unittest.TestCase):
    def test_chicago_dst_windows_have_expected_utc_duration(self):
        spring = report_window(date(2026, 3, 8), ZoneInfo("America/Chicago"))
        fall = report_window(date(2026, 11, 1), ZoneInfo("America/Chicago"))
        self.assertEqual(timedelta(hours=23), spring.end_utc - spring.start_utc)
        self.assertEqual(timedelta(hours=25), fall.end_utc - fall.start_utc)

    def test_shuffled_inputs_render_identical_bytes(self):
        first = build_fixture_package(evidence=EVIDENCE, claims=CLAIMS)
        second = build_fixture_package(
            evidence=tuple(reversed(EVIDENCE)),
            claims=tuple(reversed(CLAIMS)),
        )
        self.assertEqual(render_json(first), render_json(second))
        self.assertEqual(render_markdown(first), render_markdown(second))

    def test_previous_manifest_hash_must_match(self):
        previous = canonical_json_bytes({"schema": "selmaos.daily-log-manifest.v1"})
        manifest = build_manifest(PACKAGE, ARTIFACTS, previous_manifest=previous)
        self.assertEqual(sha256_hex(previous), manifest["prev_log_sha256"])
        with self.assertRaisesRegex(ValueError, "previous manifest digest mismatch"):
            verify_previous_manifest(previous, "0" * 64)

    def test_untrusted_markdown_is_escaped(self):
        package = build_package_with_summary("[click](javascript:alert(1))")
        rendered = render_markdown(package).decode("utf-8")
        self.assertIn(r"\[click\]\(javascript:alert\(1\)\)", rendered)
```

- [ ] **Step 2: Run renderer tests and verify the red state**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_renderer -v
```

Expected: import failure because `renderer.py` does not exist.

- [ ] **Step 3: Implement the time window and stable ordering**

```python
def report_window(day: date, timezone: ZoneInfo) -> ReportWindow:
    start_local = datetime.combine(day, time.min, tzinfo=timezone)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone)
    return ReportWindow(
        date=day,
        timezone=timezone.key,
        start_utc=start_local.astimezone(UTC),
        end_utc=end_local.astimezone(UTC),
    )


STATE_ORDER = {
    VerificationState.VERIFIED: 0,
    VerificationState.UNVERIFIED: 1,
    VerificationState.INVALIDATED: 2,
}


def result_sort_key(result: VerificationResult):
    return STATE_ORDER[result.state], result.occurred_at, result.claim.claim_id
```

- [ ] **Step 4: Implement deterministic JSON, Markdown, and manifest rendering**

```python
def render_json(package: DraftPackage) -> bytes:
    return canonical_json_bytes(package.to_mapping()) + b"\n"


def build_manifest(
    package: DraftPackage,
    artifacts: Mapping[str, bytes],
    previous_manifest: bytes | None,
) -> dict[str, JsonValue]:
    return {
        "schema": "selmaos.daily-log-manifest.v1",
        "date": package.window.date.isoformat(),
        "timezone": package.window.timezone,
        "status": "DRAFT",
        "artifacts": {
            name: sha256_hex(content)
            for name, content in sorted(artifacts.items())
        },
        "prev_log_sha256": (
            sha256_hex(previous_manifest) if previous_manifest is not None else None
        ),
        "generator_version": GENERATOR_VERSION,
        "verifier_version": VERIFIER_VERSION,
        "reviewer": None,
        "approved_at": None,
        "signature_ref": None,
    }
```

Markdown contains separate `Verified accomplishments`, `Unverified items`,
and `Invalidated claims` headings. Each non-verified entry lists every reason
and the evidence IDs used. The integrity section says `Status: DRAFT`.

- [ ] **Step 5: Run Task 3 tests**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_renderer -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add tools/daily_log_v1/renderer.py tests/test_daily_log_v1_renderer.py
git commit -m "Render deterministic daily accomplishment drafts"
```

### Task 4: Atomic and path-safe CLI

**Files:**
- Create: `tools/daily_log_v1/cli.py`
- Create: `tests/test_daily_log_v1_cli.py`

**Interfaces:**
- Consumes: the `build` CLI arguments defined in the design.
- Produces: an atomic day directory and exit codes 0, 2, 3, or 4.

- [ ] **Step 1: Write end-to-end CLI safety tests**

```python
class CliTests(unittest.TestCase):
    def test_build_writes_complete_draft_package(self):
        result = run_cli(self.workspace, "--date", "2026-09-22")
        self.assertEqual(0, result.returncode)
        day = self.workspace / "logs/2026/09/22"
        self.assertEqual(
            {"draft.json", "draft.md", "evidence.ndjson", "manifest.json"},
            {path.name for path in day.iterdir()},
        )
        manifest = json.loads((day / "manifest.json").read_text())
        self.assertEqual("DRAFT", manifest["status"])

    def test_existing_final_manifest_is_never_replaced(self):
        day = self.make_existing_day(status="APPROVED")
        result = run_cli(self.workspace, "--date", "2026-09-22", "--replace-draft")
        self.assertEqual(3, result.returncode)
        self.assertEqual("APPROVED", json.loads((day / "manifest.json").read_text())["status"])

    def test_replaced_draft_is_preserved_as_superseded(self):
        day = self.make_existing_day(status="DRAFT")
        old_manifest = (day / "manifest.json").read_bytes()
        result = run_cli(self.workspace, "--date", "2026-09-22", "--replace-draft")
        self.assertEqual(0, result.returncode)
        superseded = day.with_name(
            day.name + ".superseded." + sha256_hex(old_manifest)[:12]
        )
        self.assertEqual(old_manifest, (superseded / "manifest.json").read_bytes())

    def test_symlink_output_component_is_rejected(self):
        (self.workspace / "logs").symlink_to(self.workspace / "outside")
        result = run_cli(self.workspace, "--date", "2026-09-22")
        self.assertEqual(2, result.returncode)
        self.assertIn("symlink", result.stderr)

    def test_path_traversal_output_root_is_rejected(self):
        result = run_cli(
            self.workspace,
            "--date", "2026-09-22",
            "--output-root", "../outside",
        )
        self.assertEqual(2, result.returncode)
```

- [ ] **Step 2: Run CLI tests and verify the red state**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_cli -v
```

Expected: import failure because `cli.py` does not exist.

- [ ] **Step 3: Implement argument parsing and explicit exit mapping**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="selma-daily-log")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--date", required=True, type=date.fromisoformat)
    build.add_argument("--timezone", default="America/Chicago")
    build.add_argument("--evidence", required=True, type=Path)
    build.add_argument("--claims", required=True, type=Path)
    build.add_argument("--output-root", required=True, type=Path)
    build.add_argument("--previous-manifest", type=Path)
    build.add_argument("--previous-manifest-sha256")
    build.add_argument("--replace-draft", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run_build(build_parser().parse_args(argv))
    except ExistingOutputError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except HashChainError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
```

- [ ] **Step 4: Implement atomic directory publication**

```python
def publish_draft(
    output_root: Path,
    day: date,
    files: Mapping[str, bytes],
    *,
    replace_draft: bool,
) -> Path:
    safe_root = resolve_safe_output_root(output_root)
    target = safe_root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    assert_no_symlink_components(safe_root, target)
    guard_existing_target(target, replace_draft=replace_draft)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{day.isoformat()}.", dir=target.parent))
    try:
        for name, content in sorted(files.items()):
            write_fsynced(temporary / name, content)
        fsync_directory(temporary)
        if target.exists():
            old_manifest = (target / "manifest.json").read_bytes()
            backup = target.with_name(
                target.name + ".superseded." + sha256_hex(old_manifest)[:12]
            )
            if backup.exists():
                raise ExistingOutputError(f"superseded draft already exists: {backup}")
            target.rename(backup)
            try:
                temporary.rename(target)
            except BaseException:
                backup.rename(target)
                raise
        else:
            temporary.rename(target)
        fsync_directory(target.parent)
        return target
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
```

`resolve_safe_output_root` requires an absolute or current-working-directory
relative path whose normalized value remains beneath the current working
directory. `guard_existing_target` parses `manifest.json` strictly and
permits replacement only when its status is exactly `DRAFT` and
`--replace-draft` is present.

- [ ] **Step 5: Run Task 4 tests**

Run:

```bash
python3 -m unittest tests.test_daily_log_v1_cli -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add tools/daily_log_v1/cli.py tests/test_daily_log_v1_cli.py
git commit -m "Add atomic daily-log draft CLI"
```

### Task 5: Operator documentation and full verification

**Files:**
- Create: `docs/accomplishments/DAILY_LOG_V1.md`
- Modify: `docs/architecture/EXECUTION_TRACKER.md`
- Modify: `.github/workflows/selma-repo-health.yml`
- Test: all existing and new suites

**Interfaces:**
- Consumes: the completed CLI and fixture package.
- Produces: reproducible operator commands and repository-health coverage.

- [ ] **Step 1: Write the operator runbook**

Document this exact command:

```bash
python3 -m tools.daily_log_v1.cli build \
  --date 2026-09-22 \
  --timezone America/Chicago \
  --evidence tests/fixtures/daily_log_v1/pr18-evidence.ndjson \
  --claims tests/fixtures/daily_log_v1/pr18-claims.ndjson \
  --output-root build/daily-log-v1
```

State that the expected outcome is one verified merge claim, no verified
repository-CI claim, explicit zero-job `startup_failure` reasons, and
`status: DRAFT`. Include the exit-code table, output file meanings, size
bounds, replacement rules, and the external handoffs from the design.

- [ ] **Step 2: Add the new suites to repository health**

Append this command to the `Run portable regression suites` step:

```bash
python3 -m unittest discover -s tests -p 'test_daily_log_v1_*.py' -v
```

The existing broader `test_*.py` discovery already includes these tests; the
explicit command gives the subsystem a named CI line and must not replace the
broader discovery.

- [ ] **Step 3: Generate a PR #18 sample draft**

Run:

```bash
python3 -m tools.daily_log_v1.cli build \
  --date 2026-09-22 \
  --timezone America/Chicago \
  --evidence tests/fixtures/daily_log_v1/pr18-evidence.ndjson \
  --claims tests/fixtures/daily_log_v1/pr18-claims.ndjson \
  --output-root build/daily-log-v1
```

Expected stdout:

```text
daily log draft: verified=1 unverified=2 invalidated=1
```

Inspect `build/daily-log-v1/2026/09/22/draft.md` and confirm it does not claim
CI passed, issue #26 cleared, approval, signing, publication, or deployment.
Do not commit generated `build/` output.

- [ ] **Step 4: Run the complete portable verification**

Run:

```bash
python3 -m compileall -q SELMA0_ANDROID_AGENT_V1 adapters core tests tools
python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/generate_support_matrix.py --check
bash SELMA0_ANDROID_AGENT_V1/selma0_smoke_test_android_v1.sh
```

Expected: every command exits 0. Record exact test counts in the PR body rather
than copying counts from this plan.

- [ ] **Step 5: Validate source formats**

Run:

```bash
find . -type f -name '*.py' -not -path './.git/*' -exec python3 -m py_compile {} +
find . -type f -name '*.sh' -not -path './.git/*' -exec bash -n {} \;
python3 - <<'PY'
import json
from pathlib import Path

for path in Path(".").rglob("*.json"):
    if any(part in {".git", "build", ".venv", "venv"} for part in path.parts):
        continue
    json.loads(path.read_text(encoding="utf-8"))
print("JSON validation passed")
PY
git diff --check
```

Expected: all commands exit 0. Existing CRLF wrapper files are outside the
new-change diff check.

- [ ] **Step 6: Commit Task 5**

```bash
git add docs/accomplishments/DAILY_LOG_V1.md \
  docs/architecture/EXECUTION_TRACKER.md \
  .github/workflows/selma-repo-health.yml
git commit -m "Document and gate the daily accomplishments MVP"
```

- [ ] **Step 7: Prepare completion evidence without overstating CI**

The PR body must list:

- exact branch head SHA;
- exact local commands and counts;
- PR #18 fixture behavior;
- rollback by reverting the feature commits;
- GitHub Actions run IDs and zero-job state if the repository admission fault
  recurs;
- a link to `docs/handoffs/GITHUB_ACTIONS_STARTUP_FAILURE_2026-09-22.md`;
- the next three slices: read-only GitHub collector, review/signing flow, and
  scheduler/archive integration.

Keep the PR draft until repository CI creates real jobs, or obtain a new,
feature-specific owner-approved documented exception.
