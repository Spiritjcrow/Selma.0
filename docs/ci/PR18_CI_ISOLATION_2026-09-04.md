# PR #18 CI isolation result — 2026-09-04

## Purpose

Determine whether Gate 1 CI startup failures are caused by SelmaOS workflow contents or by GitHub Actions admission/account state.

## Procedure

1. Added a zero-dependency workflow containing one `ubuntu-latest` shell job and no marketplace actions, secrets, Gradle, Java, or Android SDK usage.
2. Observed the same immediate `startup_failure` / `BuildFailed` behavior while the normal workflows were present.
3. Temporarily removed both existing branch workflows so the bootstrap probe was the only workflow on the PR branch.
4. Changed the probe itself to force a branch push event.
5. GitHub created no workflow run for that isolated probe commit.
6. Restored both original workflows exactly and removed the temporary probe.
7. Compared the restored branch against original Gate 1 head `658fc493fb47014e3f939ffc94772dcd8d76947e`; repository file diff was empty.

## Conclusion

The observed failure occurs before SelmaOS build/test jobs are admitted. Gradle 8.9, Java 17, Android API 35, Android build-tools 35.0.0, SelmaOS tests, and third-party action steps are therefore not implicated by this failure mode.

Remaining fault domain: GitHub Actions repository/account admission state, including repository Actions enablement/policy, account Actions quota/billing state for this private repository, or a GitHub-side admission fault.

## Merge gate

Do not merge PR #18 until a GitHub-hosted runner successfully starts and the repository-health and Android validation workflows complete successfully, unless the repository owner explicitly approves a documented CI exception.
