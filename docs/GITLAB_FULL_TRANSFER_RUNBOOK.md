# Selma.0 Full GitLab Transfer Runbook

This runbook performs a real migration only when the required GitLab and GitHub credentials and the actual GitLab namespace are supplied. It intentionally refuses to invent missing destination data.

## Source identity

- GitHub repository: `Spiritjcrow/Selma.0`
- GitHub repository ID: `1157720425`
- Current source visibility: private
- GitLab target project name used by the migration runner: `SelmaOS`
- GitLab target namespace: **must be the real existing owner/group namespace**

## What the GitLab GitHub importer transfers

The transfer runner uses GitLab's official `POST /api/v4/import/github` importer with Markdown attachments and direct collaborators enabled. GitLab documents that the GitHub importer can migrate Git repository data, branches, Git LFS objects, issues, pull requests as merge requests, comments, reviews, labels, milestones, release-note content, wiki pages, direct collaborators, branch protection mappings, and supported attachments.

The importer is preferred over a plain `git push --mirror` because a Git-only mirror does not move issue and pull-request history.

## Required credentials

Do not put tokens in source files, command history, this repository, or chat messages.

Set the following only in the execution environment:

- `GITLAB_TOKEN`: GitLab personal access token with `api` scope.
- `GITHUB_IMPORT_TOKEN`: GitHub **classic** personal access token with `repo` scope. Add `read:org` when collaborator or Git LFS import requires it.

The transfer runner validates both identities before scheduling the import and does not print either token.

## Execute the repository + project-data import

From this repository checkout:

```bash
python3 tools/full_gitlab_transfer.py \
  --target-namespace "$SELMA_GITLAB_NAMESPACE" \
  --aux-bundle "$SELMA_AUX_BUNDLE" \
  --evidence-out gitlab-transfer-evidence.json
```

The environment variables `SELMA_GITLAB_NAMESPACE` and `SELMA_AUX_BUNDLE` must point to the actual namespace and the actual auxiliary Selma staging archive. The runner fails rather than substituting defaults for either one.

## Evidence gates enforced by the runner

1. GitLab token resolves to a real authenticated GitLab user.
2. GitHub token resolves the exact source repository ID `1157720425`.
3. GitLab accepts the GitHub import request and returns a real project ID.
4. The import reaches `finished`; `failed` is rejected.
5. Any non-empty GitLab `failed_relations` list is rejected.
6. Source GitHub branch/tag commit IDs are compared to GitLab branch/tag commit IDs.
7. Missing or mismatched source refs fail the run.
8. When an auxiliary bundle is supplied, it is uploaded to the destination project's GitLab Generic Package Registry as `selma-migration-assets`.
9. The auxiliary file's byte size and SHA-256 are recorded.
10. A final JSON evidence file records the actual GitLab project ID, namespace/path, web URL, visibility, import status, ref-verification result, and auxiliary-package evidence.

## Auxiliary Selma data

The GitHub importer only migrates GitHub project data. Separate Selma material inventoried from the ChatGPT Project/Library and connected Google Drive must therefore travel as an auxiliary archive rather than being silently omitted.

The current staged auxiliary archive prepared in this workspace is:

`SELMA_GITLAB_MIGRATION_STAGING_PRIVATE_2026-09-24.zip`

Recorded evidence from its creation:

- bytes: `37644331`
- SHA-256: `65f5bffa87fcf69aa64dcf16ca8ffd0336758f8ba5a4fc68b48b3e27a058532a`

The archive remains private migration material. Restricted account-defense material inside it must not be republished into a public project.

## Credential quarantine

A connected Drive inventory surfaced one credential-like item. It is deliberately excluded from source-control migration. Any live credential must be rotated or revoked and recreated in GitLab only as a protected CI/CD variable or another appropriate secret store.

## Canonical cutover

GitLab becomes canonical only after:

- GitLab reports the GitHub import as finished with no failed relations.
- Branch/tag ref verification passes.
- The auxiliary package upload succeeds and its SHA-256 evidence is recorded.
- GitLab creates and executes real CI jobs from `.gitlab-ci.yml`.
- Imported issues and merge requests are spot-checked against the source inventory.
- Any importer warnings are reconciled.
- GitHub is retained until all verification gates pass.

No deletion of the GitHub source is part of this transfer.
