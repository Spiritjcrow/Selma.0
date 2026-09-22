# GitHub Actions startup-admission handoff

Prepared: 2026-09-22  
Repository: `Spiritjcrow/Selma.0` (private)  
Owner/operator: `Spiritjcrow`  
Repository tracker: issue #26

## Intended recipient

GitHub Support engineer with access to private-repository Actions admission,
workflow-registration, entitlement, and billing/policy diagnostics.

## Copy-ready support request

**Subject:** Private repository Actions runs use synthetic `BuildFailed`
workflow and end in `startup_failure` before creating jobs

GitHub Actions in private repository `Spiritjcrow/Selma.0` is not reaching
workflow job creation. Push and pull-request events immediately produce runs
with all of these properties:

- workflow name is empty;
- workflow path is `BuildFailed`;
- workflow ID is `329988227`;
- conclusion is `startup_failure`;
- the jobs endpoint returns an empty array;
- no checked-in workflow step, action, runner, or repository test executes.

Please inspect the repository/account Actions admission state and the
synthetic/orphaned workflow registration `329988227`. Please purge or
re-index the stale registration if appropriate, confirm Actions
entitlement/billing/policy permits job creation for this private repository,
and help us obtain one run with a real job ID.

The checked-in workflows are present on the default branch, parse locally, use
`permissions: contents: read`, and reference ordinary first-party actions.
A separate zero-dependency one-job probe also failed before job creation, so
the failure is not isolated to a particular repository build step.

## Current exact evidence

Default branch after PR #18:

- branch: `main`
- commit:
  `9a7d3c02036aadbb7f7cf03a03877987af9dda11`
- commit URL:
  https://github.com/Spiritjcrow/Selma.0/commit/9a7d3c02036aadbb7f7cf03a03877987af9dda11

Runs on that exact commit:

| Run | Event | Created UTC | Result | Workflow name | Path | Workflow ID | Jobs |
|---:|---|---|---|---|---|---:|---:|
| [35680991511](https://github.com/Spiritjcrow/Selma.0/actions/runs/35680991511) | push | 2026-09-22 02:51:18 | `startup_failure` | empty | `BuildFailed` | 329988227 | 0 |
| [35762629076](https://github.com/Spiritjcrow/Selma.0/actions/runs/35762629076) | push | 2026-09-22 17:44:15 | `startup_failure` | empty | `BuildFailed` | 329988227 | 0 |

Immediately before merge, exact PR #18 head
`6540354b4ec461f8b6dbe31c743f133c183f9b8e` produced:

| Run | Event | Result | Workflow path | Jobs |
|---:|---|---|---|---:|
| [35680825688](https://github.com/Spiritjcrow/Selma.0/actions/runs/35680825688) | push | `startup_failure` | `BuildFailed` | 0 |
| [35680828475](https://github.com/Spiritjcrow/Selma.0/actions/runs/35680828475) | pull_request | `startup_failure` | `BuildFailed` | 0 |

Earlier affected evidence includes run
[33913982025](https://github.com/Spiritjcrow/Selma.0/actions/runs/33913982025)
on PR #18 head `772c9359c7ba13669f27d847796e9d2525b83ab4`.
It has the same empty-name, `BuildFailed`, zero-job signature.

## Repository-side isolation already performed

- Both checked-in YAML workflow files were confirmed present and readable.
- Workflow YAML was parsed locally.
- Python, shell, JSON, and repository regression commands pass locally.
- A minimal one-job, zero-dependency `ubuntu-latest` probe was tried and
  produced the same pre-job failure.
- A third-party CodeRabbit status could see the affected commit, which shows
  the GitHub commit/PR exists and is visible to integrations.
- Retrying affected runs was rejected because no runnable job state existed.
- We did not broaden token permissions, add secrets, disable security
  controls, or bypass the existing authorization/control plane.

## Expected behavior

Dispatching a checked-in `push`, `pull_request`, or
`workflow_dispatch` workflow should create at least one job object with a
real job ID. A repository command may subsequently pass or fail; either is
valid diagnostic evidence. The current failure happens before that boundary.

## Requested support actions

1. Inspect workflow registration ID `329988227` and explain why it resolves
   to an empty-name `BuildFailed` workflow.
2. Check private-repository Actions entitlement, billing/usage suspension,
   organization/repository policy, and required workflow approval state.
3. Purge or re-index the stale/synthetic workflow registration if it is
   intercepting dispatch.
4. Trigger or permit a minimal `ubuntu-latest` workflow and confirm that its
   jobs endpoint contains a real job ID.
5. Identify any account-owner action required, with the exact Settings page
   and value that must change.

## Safe acceptance test after repair

Use a manual dispatch of the repository-health workflow already on `main`.
Acceptance requires:

- a nonempty workflow name and checked-in workflow path;
- at least one real job ID;
- job steps visible through the Actions jobs API;
- the run tied to the exact `main` SHA used for the test.

Do not treat a run-level `success` with zero jobs as acceptance.

After one real job exists, rerun the current `main` workflows and record
actual job/step results. Only then should issue #26 be closed or Gate 1 issue
#15 claim repository CI evidence.

## Information safe to attach

- URLs for the runs listed above;
- JSON metadata for each run and its empty jobs response;
- issue #26 discussion;
- the two checked-in workflow YAML files;
- repository visibility and Actions settings screenshots with account,
  payment, token, and personal information redacted.

Do not attach access tokens, cookies, secrets, full billing instruments,
private keys, or unredacted environment dumps.

## Transfer status

This handoff is complete and ready to paste into GitHub Support. Sending it,
changing billing or repository policy, and granting support access require the
repository/account owner.
