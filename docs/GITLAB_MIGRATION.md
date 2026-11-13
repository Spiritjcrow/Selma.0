# Selma.0 GitLab Migration Runbook

## Verified source

- GitHub repository: `Spiritjcrow/Selma.0`
- Repository ID observed through the authenticated GitHub connection: `1157720425`
- Visibility observed: private
- Default branch: `main`
- Current verified `main` commit at refresh: `f19a514846e7dcd26c90b461d7107d73dc8fc163`
- Migration-preparation branch: `selma-gitlab-migration-v2`

No GitLab destination is recorded here because no authenticated GitLab project has yet been made available to this workspace.

## Required migration path

Use GitLab's GitHub importer rather than a repository-only copy when the destination becomes available. GitLab's importer is designed to migrate Git repository data together with issues, pull requests as merge requests, comments, reviews, labels, milestones, releases, collaborators, branch protection mappings, Git LFS objects, wiki pages, and selected Markdown attachments.

For GitLab.com:

1. Sign in to GitLab.
2. Create a new project/repository.
3. Choose **Import project** and then **GitHub**.
4. Authorize access to the GitHub account that can read the private `Spiritjcrow/Selma.0` repository.
5. Select `Spiritjcrow/Selma.0`.
6. Enable Markdown attachment import so project evidence embedded in issues and pull requests is not intentionally omitted.
7. Import collaborators if the GitLab namespace is intended to preserve collaborator membership.
8. Start the import and wait for GitLab to report **Complete**. A **Partially completed** or **Failed** state is not accepted as completion.

Do not delete, archive, or rewrite the GitHub source while the import is incomplete.

## Repository integrity gate

After GitLab reports a complete import, run from an authenticated machine that can read both private repositories:

```bash
python3 tools/verify_gitlab_migration.py compare-refs --destination "$SELMA_GITLAB_REMOTE"
```

`SELMA_GITLAB_REMOTE` must be the actual GitLab clone URL. The command exits nonzero when a source branch/tag is missing or points to a different object.

The GitHub source defaults to the verified source URL `https://github.com/Spiritjcrow/Selma.0.git`.

## GitLab CI gate

This branch adds `.gitlab-ci.yml` with three evidence stages:

- Python source compilation for the current core, adapters, Android/Termux runtime, tests, and tools.
- The two unittest suites and support-matrix check documented by the current repository README.
- A pipeline evidence artifact containing the real GitLab commit SHA, project/ref identity, pipeline/job IDs, and SHA-256 inventory of the checked-out workspace.

A pipeline is considered real evidence only when GitLab creates actual jobs and those jobs execute. A pipeline configuration existing in the repository is not proof of execution.

## Project-data verification gate

Before declaring GitLab canonical, verify in the GitLab project UI/API that the imported project contains the expected GitHub project records, including open development work, closed/merged work, comments/reviews, labels/milestones used by the project, releases if present, and attachments selected for import.

GitLab documents some mapping limitations between GitHub references and GitLab issue/merge-request references. Those mapping differences are not repository corruption, but any entity explicitly reported as failed by the importer must be reconciled before completion.

## Canonical cutover rule

GitLab becomes the Selma.0 source of truth only when all of the following are true:

- GitLab import status is Complete.
- Branch/tag ref verification passes.
- GitLab CI creates real jobs and the repository validation jobs execute.
- GitLab's imported issues/merge requests and selected attachments are reviewed for failed entities.
- The source repository remains recoverable until the GitLab copy has passed these gates.

Only after those gates should GitHub be treated as a historical/archive source. No deletion is part of this runbook.
