# SelmaOS dual-role portable QA checkpoint (2026-10-28 CDT)

**Scope:** draft PR #50 / issue #49, exact head before this documentation-only commit: `87a3e093b9aaa270c9185131c22ef9a69b99dd5e`. This is **source-subset verification**, not full repository, independent White-phone, Android/Termux, APK, or GitHub Actions evidence.

## Reproduction and provenance

Five Python files were reconstructed into a disposable local workspace from an earlier audit bundle plus the current authenticated GitHub source, and verified **byte-for-byte** using Git blob SHA-1 before running. These are *not* independently cloned checkout bytes:

| GitHub path | Verified Git blob SHA |
| --- | --- |
| `core/duo_handoff.py` | `062a80383e7b3a716ff33ac8e69788dfaaf20e3b` |
| `tests/test_duo_handoff.py` | `263624113b086d6b065393c3600089c63b428ca3` |
| `tests/test_duo_mapping_keys.py` | `62f0edda816aab9578e76c66b087314a09b053a6` |
| `tests/test_duo_cli_regression.py` | `7b30830d94452c4df6d14f813caefa64f526d2e0` |
| `tools/selma_duo_validate.py` | `35e7cf16102742605930f2b6b077a075c77b5568` |

Local interpreter: Python 3.13.5. Command, from the reconstructed subset root:

```sh
PYTHONWARNINGS=error python3 -m unittest discover -s tests -p 'test_duo*.py' -v
python3 -m py_compile core/duo_handoff.py tools/selma_duo_validate.py tests/test_duo_handoff.py tests/test_duo_mapping_keys.py tests/test_duo_cli_regression.py
```

**Observed:** 39/39 checked-in test methods PASS, unittest exit 0; `py_compile` exit 0. Local text log SHA-256: `9cc53f92acaad05c3f3ed5a5d2fd1895021e74836738b319632e3708705f64c6`. Log exists only in the local run artifact, not in GitHub; the hash is not a claim that GitHub CI ran. Subprocess tests exercised local Python CLI without network/device access.

## Black → White → UltraViolet logical review

- **Black:** produced a reproducible, reversible documentation-only evidence checkpoint, with exact source-blob bindings; no runtime/permission changes.
- **White (same authenticated automation, not independent White device/account):** ran the exact five-file reconstructed checked-in Python subset and compilation, both PASS. Full checkout, actual phone, independent GitHub reviewer, APK, offline runtime and local model tests **NOT_RUN**.
- **UltraViolet:** source subset PASS, independent acceptance **BLOCKED**. Keep PR **DRAFT**. GitHub Actions #26 has historically returned `startup_failure` and zero jobs; this local test does not resolve admission or authorize merge.

**Next owner:** independently authenticated White Tester. **Next action:** fetch the precise PR head into an authorized full checkout, independently run the same commands and owned-device rootless/offline QA plan; then report observed results in #49 or PR #50. Confirm actual Actions jobs and separate #43 security acceptance before any merge/deployment. No credential, invite, account, policy, release, protected-branch or production change is authorized by this checkpoint.
