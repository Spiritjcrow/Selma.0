# Selma Candidate Forge v0.1 — offline-first code proposal worker

**Status:** functional review-only source prototype. Its own 14 isolated fixture tests were executed in an ephemeral Linux test directory on 2026-10-30: **14/14 PASS**. The exact tested source and tests were committed to this branch and compared with the local originals (byte counts and FNV fingerprints match). The full private repository, Android builds, actual Ollama inference, and Android device tests are **NOT VERIFIED**.

## Purpose

This is the next component after PR #94's bounded local build-on-commit loop. It can ask a locally running Ollama model to propose **one replacement for one existing source file** and produce a unified diff for owner review. It is not an open-ended autonomous engineer. In particular it never edits tracked source, runs returned code, creates a Git branch/commit/PR, merges, distributes binaries, accesses signing credentials, or publishes an app. Do not pass a forged diff to a host-side test runner without independent review and isolation.

The model endpoint is hardcoded to **http://127.0.0.1:11434/api/generate**, with environment proxies disabled and redirects rejected. If Ollama is not running there, this prototype fails closed. It does not attempt cloud fallback. Source content is locally transmitted to that exact process (which the operator must trust).

## Setup

- A trusted, clean, complete local checkout on the candidate branch, Python 3.12+ and Git.
- A local Ollama installation with a model supporting the needed code context; for example run your own locally installed model through Ollama. The application does not fetch models or start a server.
- Stop switch: file SELMA_BUILD_STOP in the checkout Git control directory. As in #94, creating it disables the worker.

Create a **task JSON outside the checkout** containing the exact *current candidate branch* HEAD:

~~~json
{
  "base_sha": "REPLACE_WITH_YOUR_EXACT_40_CHARACTER_GIT_HEAD",
  "target": "core/example.py",
  "goal": "Describe one small bug fix or unit-testable improvement without widening permissions.",
  "model": "YOUR_INSTALLED_LOCAL_MODEL_TAG"
}
~~~

The target must be a real tracked-in-checkout source file under SELMA0_ANDROID_AGENT_V1, SELMA0_ANDROID_NATIVE_V1, core, adapters, tools, or tests and must have a .py, .java, .kt, or .md extension. Replace core/example.py with an actual file that exists. No filesystem traversal, symlink target, arbitrary endpoint, build script or credentials file is accepted.

Example command from the complete checkout root:

~~~sh
python tools/selma_candidate_forge.py --task /path/to/candidate-task.json
~~~

Output is placed in the Git control directory under selma-forge/<unique-id>.diff and selma-forge/<unique-id>.json, with restricted file permissions. Review the diff and manifest; the normal tracked Git checkout remains untouched. The manifest uses status REVIEW_ONLY_NOT_EXECUTED.

## Verification and red lines

From the candidate branch:

~~~sh
python -m unittest discover -s tests -p 'test_selma_candidate_forge.py' -v
~~~

The tests use temporary Git checkouts and mock model output, no live model or remote network. They cover clean and dirty revisions, base SHA checks, strict JSON duplicate rejection, path traversal, symlinks, secrets markers, schema and target mismatch, unchanged/empty content, kill switch, source mutation, redirect prevention, and review-only output.

These tests do **not** assess generated code correctness or prove runtime sandbox security, because no generated code is executed. Before applying a candidate, an independent reviewer should validate provenance, scope, secrets, dependencies, safety, test coverage and changes. Only reviewed changes should be copied to a separate development branch and tested with PR #94's bounded local validator on an isolated, low-privilege runner. This worker itself is not a hardened sandbox for executing untrusted code.

## Dependencies and release path

This draft branch stacks on PR #94, which stacks on PR #89. PR #78 (Android native UI) and PR #95 (API 36 proposal) are independent release-track branches. Do not merge or auto-cherry-pick speculative model changes into these branches. The Play Store commercialization gate is issue #96. Security hardening issue #43 and actual Android acceptance remain release blockers. No background daemon, Google Play upload, paid advertisement, or release signing is authorized by this component.
