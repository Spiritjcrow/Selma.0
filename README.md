# Selma.0

Synthetic Consciousness System Operator Assistant Collaborator

## Active Android build

The current production-direction implementation is:

`SELMA0_ANDROID_AGENT_V1/`

This build is designed for Android 13+ with Termux as the immediate runtime and GitHub Codespaces as the development environment.

### Current implemented core

- Android/Termux Python runtime
- Device-local HTTP API and mobile chat UI
- Persistent SQLite conversation memory
- Offline-first OpenAI-compatible LLM routing
- Optional online fallback configured only through environment variables
- Codespaces devcontainer
- Unique `SELMA0_..._V1` namespace for project artifacts

### Termux install

Clone the repository, enter it, and run:

```bash
chmod +x SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh
./SELMA0_ANDROID_AGENT_V1/selma0_bootstrap_termux_android_v1.sh
~/SELMA0_ANDROID_AGENT_V1/selma0_start_android_v1.sh
```

Then open:

`http://127.0.0.1:8765`

### Offline LLM

Selma.0 first attempts an OpenAI-compatible local endpoint at:

`http://127.0.0.1:8080/v1`

The next implementation milestone is the Android-local llama.cpp launcher/model profile so this endpoint is supplied entirely on-device.

See `SELMA0_ANDROID_AGENT_V1/SELMA0_ANDROID_AGENT_V1_ARCHITECTURE.md` for the production roadmap.

## Gate 1 cross-platform contracts

The platform-neutral contract increment is under:

- core/ for capability, result, cancellation, deadline, and offline-bootstrap contracts;
- adapters/ for fail-closed implementations and platform evidence manifests;
- docs/architecture/ for current truth state, migration map, execution tracker, and generated support matrix;
- tests/ for offline/degraded-state contract tests.

Run the portable evidence suite:

~~~bash
python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/generate_support_matrix.py --check
~~~

The support matrix records repository evidence only. It does not claim APK installation, physical-device behavior, offline model output, live avatar rendering, or sensor results without direct evidence.
