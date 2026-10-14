# SelmaOS temporary multi-host migration plan (2026-10-14)

## Actual status
- GitHub connected; existing sources preserved.
- 12 source repositories verified: 5 private and 7 public.
- A machine-readable source inventory exists in [repository-inventory-2026-10-14.json](repository-inventory-2026-10-14.json).
- GitLab and Bitbucket accounts are NOT connected to this chat; no destination repositories, imports or tested hosted APKs exist yet.
- This branch contains a staged root `.gitlab-ci.yml` for EmberBot, with Python tests, a manually gated Android build, and APK integrity verification.
- Read-only, authenticated GitHub access is still functional through the ChatGPT GitHub connector. The account 2FA/mobile phone issue and GitHub Actions startup blocker #26 remain unresolved.

## Independent hosts
1. **GitLab**: primary alternate, private repos; supports GitHub code and project-metadata imports.
   Official guide: https://docs.gitlab.com/user/project/import/github/
2. **Bitbucket Cloud**: secondary private repo copies, independent from GitHub/GitLab.
   Official guide: https://support.atlassian.com/bitbucket-cloud/docs/import-a-repository-from-github-or-gitlab/
3. **Encrypted offline/cloud archives**: retain Git bare bundles with all references, LFS separately, explicit content digests and restoration drills. Avoid placing recovery codes, PATs or passwords in any repo, ZIP or CI variable in plain text.
4. **Codeberg**: optional only for approved free/libre projects, not a general private proprietary mirror.
   Official policy: https://docs.codeberg.org/getting-started/faq/

## Initialization requirements
- Sign in to GitLab and Bitbucket under accounts controlled by the owner and create empty PRIVATE destination repos, or use GitLab's dedicated GitHub importer.
- Use approved owner-authorized credentials in the providers' secure interfaces, not ChatGPT, issues, commits, or command arguments.
- Import `Spiritjcrow/Selma.0` with ALL branches, in particular `feature/emberbot-mines-research-20261012` (PR #56); do not flatten this into main.
- For remaining 11 repos, preserve source branch and tag refs and inspect project history, release assets, Wikis, LFS, dependencies, and GitHub issue/PR metadata independently.
- Use a safe non-force authenticated mirror tool that refuses nonempty targets and verifies each branch/tag SHA after copy.
- Confirm runner quota/billing before enabling `EMBERBOT_AUTO_APK=true` in GitLab CI. Manual by default; the validated source Python unit tests do not establish Android installation.
- Keep GitHub originals; do not delete/move/merge or make private data public before destination validation.

## Acceptance evidence
- Each target repository URL is real, private, accessible, with matching expected source heads/tags and a tested fresh clone.
- Migrated issues, comments and PRs reviewed; omissions documented.
- Android APK artifact produced by a real CI job, ZIP and manifest checked, then tested on actual Android hardware.
- At least one independent encrypted archive successfully restored into a disposable local workspace.
- All backups accessed without exclusive dependence on the locked GitHub phone/2FA account.

This is a reversible staging plan, NOT a claim that cross-provider migration has completed.
