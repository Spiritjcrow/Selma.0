# Reproducing the SelmaOS WP-01 baseline and Gate 1 increment

Run the baseline checks from the repository root. The WP-01 evidence snapshot
uses main commit e429da887eb183981d954a39450886b335a5e9b5; the Gate 1 and wrapper
commands require the PR #18 branch or its eventual merge commit.

## Environment

~~~bash
python3 --version
java -version
gradle --version
sdkmanager --version
~~~

The exact-main baseline environment had Python 3.12.13 and OpenJDK 17.0.20;
Gradle and the Android SDK were unavailable there. PR #18 was additionally
verified with Temurin JDK 17.0.20.1, the checked-in Gradle 8.9 wrapper, Android
platform 35 revision 2, and build-tools 35.0.0.

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

## Gate 1 contracts (PR #18)

~~~bash
python3 tools/generate_support_matrix.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
~~~

## Android build gate (PR #18)

PR #18 includes a Gradle 8.9 wrapper with the official distribution checksum.
The workflow specifies JDK 17, Android platform 35, and build-tools 35.0.0:

~~~bash
cd SELMA0_ANDROID_NATIVE_V1
./gradlew --no-daemon --stacktrace :app:lintDebug
./gradlew --no-daemon --stacktrace :app:testDebugUnitTest
./gradlew --no-daemon --stacktrace :app:assembleDebug
~~~

Do not claim these tasks passed unless that toolchain is present and the commands complete successfully. APK installation, overlay behavior, permissions, and performance require a separate owned-device report.

Local PR-branch result on 2026-09-01: **PASS**. The combined command completed
all three tasks; lint reported 0 errors and 2 warnings, the unit-test task had
no sources, and `assembleDebug` produced a 9,081-byte APK with SHA-256
`37c49bf9d0f1bcb340bae2193b0ef95a7f3466d2f0bdeb7f87b5fdf68851298a`.
This proves buildability in that toolchain, not installation or behavior on an
owned Android device.
