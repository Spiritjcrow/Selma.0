# Reproducing the SelmaOS WP-01 baseline

Run from the repository root at main commit e429da887eb183981d954a39450886b335a5e9b5.

## Environment

~~~bash
python3 --version
java -version
gradle --version
sdkmanager --version
~~~

The reproduced environment had Python 3.12.13 and OpenJDK 17.0.20. Gradle and the Android SDK were unavailable.

## Repository health

~~~bash
set -euo pipefail

find . -type f -name '*.py' \
  -not -path './.git/*' \
  -not -path '*/.venv/*' \
  -not -path '*/venv/*' \
  -exec python3 -m py_compile {} +

find . -type f -name '*.sh' \
  -not -path './.git/*' \
  -not -path '*/node_modules/*' \
  -exec bash -n {} \;

python3 - <<'PY'
import json
from pathlib import Path

for path in Path(".").rglob("*.json"):
    if any(part in {".git", "node_modules", ".venv", "venv", "build", "dist"} for part in path.parts):
        continue
    json.loads(path.read_text(encoding="utf-8"))
print("JSON validation passed")
PY
~~~

## Existing command/device suite

~~~bash
python3 -m compileall -q SELMA0_ANDROID_AGENT_V1
python3 -m unittest discover \
  -s SELMA0_ANDROID_AGENT_V1/tests \
  -p 'test_*.py' \
  -v
bash SELMA0_ANDROID_AGENT_V1/selma0_smoke_test_android_v1.sh
~~~

Baseline result: 55 unit/regression tests passed and the isolated loopback smoke test passed without device effects.

## Gate 1 contracts

~~~bash
python3 tools/generate_support_matrix.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
~~~

## Android build gate

The current-main workflow specifies JDK 17, Gradle 8.9, Android platform 35, and build-tools 35.0.0:

~~~bash
cd SELMA0_ANDROID_NATIVE_V1
gradle --no-daemon --stacktrace :app:lintDebug
gradle --no-daemon --stacktrace :app:testDebugUnitTest
gradle --no-daemon --stacktrace :app:assembleDebug
~~~

Do not claim these tasks passed unless that toolchain is present and the commands complete successfully. APK installation, overlay behavior, permissions, and performance require a separate owned-device report.
