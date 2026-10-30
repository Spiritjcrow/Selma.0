# Selma Candidate Docker test gate v0.1 — experimental

This draft stacks on PR #97 (review-only model candidate generator + static reviewer), which stacks on #94 and #89. It adds a bounded, optional offline Docker Linux-container test executor for one independently reviewed candidate. It does not touch protected branches, create commits, deploy, sign APKs, publish an app, buy ads or grant model output host permissions.

## Current evidence — 2026-10-30

- **32/32 isolated fixture tests PASS**: 14 candidate generator + 9 static reviewer + 9 test-gate/snapshot checks.
- Python compileall on the worker sources and tests: PASS in the isolated test workspace.
- Test-gate fixtures use an actual git archive of a tiny disposable Git repository, patch application to a temporary copy, SHA-256 verification, and confirm tracked source remains unchanged.
- **No Docker daemon is available in this execution environment.** Real Docker execution, live Ollama inference, complete private Selma checkout tests, Android Gradle/device tests, and any Google Play release remain NOT_RUN or NOT_VERIFIED.

## Owner-controlled operating sequence

1. On a trusted computer with Git, Python 3.12+ and Docker running Linux containers, check out this branch as a clean complete private Git repository.
2. Run the candidate forge using a trusted loopback-only local Ollama model and inspect its saved .diff (see docs/SELMA_CANDIDATE_FORGE.md).
3. Run the static reviewer with the saved candidate ID. Only continue after separately reviewing the diff and its scope.
4. Pre-load a trusted official Python image using its immutable digest; verify the digest and ensure the image includes a supported Python interpreter. Never substitute an unpinned image or allow network pulls.
5. Run the gate:

~~~sh
python tools/selma_candidate_sandbox.py --candidate-id YOUR_CANDIDATE_ID --image "python@sha256:YOUR_VERIFIED_64_HEX_DIGEST" --timeout-seconds 300
~~~

The command requires a previously successful static report, rechecks source revision and artifact hashes, extracts committed source to a temporary directory, applies the one-file diff, checks file digest/Python AST, and invokes a fixed Python unittest discovery command inside Docker.

### Fixed isolation controls

- Docker network disabled and remote image pulling disabled.
- Read-only root and source mount; non-root numeric user; all capabilities dropped; no-new-privileges.
- CPU, RAM and process limits; bounded 30–600-second deadline; restricted temporary filesystem.
- No Docker socket, host home mount, host credentials, Android signing keys or remote actions.
- Owner kill switch in the Git control directory named SELMA_BUILD_STOP.
- Source checkout unchanged; result written to an internal .sandbox.json file and always requires human review.

This reduces risk but is not a security guarantee. Docker, OS, image and source code can contain flaws. Never use privileged or untrusted build hosts. Model-generated changes may contain harmful logic despite syntactic/test success, so review, trusted test evidence, permissions and independent release approval remain mandatory.

## Independent verification

~~~sh
python -m unittest discover -s tests -p 'test_selma_candidate_*.py' -v
~~~

Dependencies must already exist inside the pinned image: the runner cannot download packages, and the plain Python image does not compile Android APKs. Android acceptance, auth hardening #43 and Play Store release #96 are separate unresolved gates.
