# Selma° Perceptual Operator — reproducible synthetic smoke test (proposal)

**Status:** source/configuration proposal. It is not an authenticated brain-computer interface, sensor detector, or validated cognition engine. All neuronal spikes here are **simulated** from a clearly labeled synthetic CSV fixture.

## Where it runs

- **Google Colab:** The existing Drive v0.2 notebook is known to have run on a user-authorized Colab session; it stores `perceptual_report.json` and `reactor_spikes.csv` under `MyDrive/PerceptualData/results`.
- **GitHub Actions:** This PR only stages an isolated, low-permission, weekly + manual synthetic smoke-test workflow. GitHub Actions currently reports `startup_failure` with **zero jobs** for this repository (see issue #26). No successful cloud job is claimed. The weekly schedule becomes eligible **only after merge to the default branch** and only if GitHub admits jobs.
- **Android Termux:** Not used as an unattended runner. Older Termux versions with retired Bintray/termux.org sources must be backed up and repaired separately.

## Pipeline

`SYNTHETIC_demo.csv` → `simulator.py` (time-varying Poisson inputs + LIF/STDP) → `perceptual_report.json` + `reactor_spikes.csv` → `verify_run.py` (fail-closed audit) → `verification.json` + `reactor_raster.png` + `learning_progression.png`.

The verifier checks the dataset SHA256, original filename, sample interval, spike index bounds, per-epoch spike totals, and numeric weight range; a mean weight >=0.9 is **flagged as saturation risk**, not accepted as proof of improved learning.

## Manual local run (Linux/Python 3.11; virtual environment recommended)

```sh
python -m pip install 'numpy>=1.26,<3' 'pandas>=2,<3' 'matplotlib>=3.8,<4' 'brian2>=2.8,<3'
python -m unittest discover -s labs/perceptual_operator -p 'test_*.py' -v
python labs/perceptual_operator/simulator.py labs/perceptual_operator/SYNTHETIC_demo.csv --epochs 5 --out-dir perceptual-artifacts
python labs/perceptual_operator/verify_run.py labs/perceptual_operator/SYNTHETIC_demo.csv perceptual-artifacts/perceptual_report.json perceptual-artifacts/reactor_spikes.csv --out-dir perceptual-artifacts
```

## Boundaries and follow-ups

- No Drive OAuth, user files, tokens, or secrets are committed to the repository; the workflow **does not** access private Google Drive datasets or write back to Drive. Those steps require a separate credentialed runner integration and explicit review.
- Do not publish any actual EEG/user-recording dataset as a public CI artifact. Consent and data protection come first.
- Do not silently fall back to random input when the intended dataset is missing.
- The repository's current Android release/PR CI work remains untouched. GitHub issue #26 is the prerequisite for confirming this workflow actually executes.
- Human approval is required before promoting this draft PR to the default branch or claiming CI PASS.