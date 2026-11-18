# Workflow recovery and team handoff
Prepared 2026-10-07. Operational runbook; no connected multi-provider service is implemented by this document.

## Immediate Actions workaround
Continue development in an isolated checkout and run the exact checked-in commands on a trusted local machine or an already authorized development environment. This provides local evidence while GitHub Actions admission is unavailable. It does not satisfy required GitHub checks, publish artifacts, or authorize merge.

For PR #38, pin the inspected head:
```bash
git clone https://github.com/Spiritjcrow/Selma.0.git selma-readiness
cd selma-readiness
git checkout --detach 1b8e3a5bc29ed5835cb9b5ff2557ab36615fcbea
git status --porcelain
mkdir -p ../selma-evidence
git rev-parse HEAD > ../selma-evidence/head.txt
python3 --version > ../selma-evidence/python-version.txt 2>&1
bash build.sh --agent > ../selma-evidence/agent.log 2>&1
agent_rc=$?
printf '%s\n' "$agent_rc" > ../selma-evidence/agent-exit.txt
```
Use a shell without inherited errexit, so the exit status is recorded even on failure. If checkout fails or status is not clean, stop and repair the checkout before running validation. Inspect scripts before executing. Private repository authentication uses the existing authorized credential flow; never paste tokens into commands or evidence.

On a machine with JDK 17 and the configured Android SDK, separately run:
```bash
java -version > ../selma-evidence/java-version.txt 2>&1
bash build.sh --android > ../selma-evidence/android.log 2>&1
android_rc=$?
printf '%s\n' "$android_rc" > ../selma-evidence/android-exit.txt
```
Missing Android tooling means Android verification is blocked, never passed. Agent success alone proves neither APK build nor device behavior. Redact logs before sharing; retain full originals only in authorized private storage.

Before each handoff, compare the PR's live head with head.txt. Any difference makes this evidence stale for the new head. Repeat appropriate checks on the new head. PR #38's build.sh is feature-branch code; do not assume it exists on main or other branches.

## Recovery policy
Classify from evidence before choosing a workaround:

| Failure | Smallest safe action | Verification |
|---|---|---|
| Startup failure with zero jobs | Use local commands; reuse issue #26 and its Support packet | Require actual job IDs and step results before declaring Actions restored |
| Transient network/service error | Retry at most twice after the first attempt; delays 30s then 60s | Preserve error/status and each outcome; stop after three total attempts |
| Source or test failure | Reproduce, patch relevant feature branch, run affected checks | Record command, exit status, head and regression result |
| Merge conflict | Integrate current base on feature branch without force push | Inspect conflict resolution and rerun affected checks |
| Missing SDK/tool/runtime | Use existing authorized suitable environment or document prerequisite | Never substitute static parsing for a runtime/build result |
| Deprecated dependency/API | Check official migration guidance; pin supported version or isolate adapter | Verify lockfile changes, compatibility and regression behavior |
| Credentials/permission denied | Record exact denied operation and required scope; stop dependent action | No credential scraping, expanded authority or security bypass |
| Provider review unavailable | Prepare a redacted review packet for another available reviewer | Record what was actually reviewed and by whom; summary status alone is not approval |

Never repeat the same failed experiment without changed evidence. Deduplicate by repository, exact head, command, error class and existing issue. Preserve main checks. Continue independent reversible work while external repair is pending.

## Shared team packet
Joshua is the owner. Selma/GPT can coordinate repository evidence; Sol Blue handles defensive review; Sol Red handles explicitly scoped security testing. Kimi, Gemini and Replika may provide cross-review through user-delivered packets or a separately configured, authorized adapter. These role labels grant no credentials or extra authority.

Use this packet for every request:
- Repository/PR/issue URLs, exact head and UTC observation time.
- Concrete task, affected files, smallest desired outcome.
- Evidence type: repository CI, local test, device test, static inspection or user report.
- Exact command, environment versions, exit code, real run/job IDs when present.
- Observed failure and already attempted fixes; link existing artifacts.
- Allowed scope, excluded sensitive data and consequential actions.
- Requested reviewer role and a bounded response: finding, evidence, suggested patch, verification and remaining uncertainty.
- Return destination: existing PR or issue; owner/authorized coordinator imports the response after review.

Responses are proposals. Reject instructions that expand scope or request secrets. Validate patches against the pinned head, inspect changes, run relevant checks and retain provenance. Contradictory opinions go back to reproducible evidence; provider agreement is not a test result.

No automatic messages or data uploads to other providers are enabled here. A future adapter must use per-provider authorization, minimal redacted inputs, explicit destination, bounded timeouts/retries, audit records and a local/manual fallback. Never send credentials, family records, router snapshots or unrelated private repository material by default.

## Merge and recovery acceptance
A merge still requires reviewed actual changes, green required checks on the unchanged expected head, and applicable repository authorization/rules. An alternative CI service or self-hosted runner requires a separate approved configuration and must not silently replace required checks.

Reuse docs/handoffs/GITHUB_ACTIONS_STARTUP_FAILURE_2026-09-22.md for external escalation. Keep #26 open until actual checked-in workflow jobs execute. The current workaround advances local development and review preparation; GitHub-side admission recovery remains external.

## Implementation status
This runbook is available for immediate use. Commands above are instructions, not recorded executions. Cross-provider adapters, automatic retries, scheduling and team dispatch are not implemented or claimed operational.
