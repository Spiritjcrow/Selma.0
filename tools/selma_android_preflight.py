#!/usr/bin/env python3
"""Read-only, no-payment Android toolchain preflight for Selma native builds.

Run from any working directory:
    python tools/selma_android_preflight.py

A PASS means only the named local prerequisites are present. It does not
build, sign, install, or test an APK; it does not validate dependency caches.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent.parent / 'SELMA0_ANDROID_NATIVE_V1'
SDK_API = '35'
BUILD_TOOLS = '35.0.0'


def java_major(version_text: str) -> int | None:
    """Extract the Java major from Java/OpenJDK -version output."""
    match = re.search(r'version\s+"(1\.)?(\d+)', version_text)
    if not match:
        return None
    return int(match.group(2))


def check(project: Path, sdk: Path | None, java_text: str | None, *, windows: bool = False) -> list[str]:
    """Report missing hard prerequisites; no side effects on inputs."""
    failures: list[str] = []
    if not project.is_dir():
        failures.append('Missing native project: SELMA0_ANDROID_NATIVE_V1')
    if java_text is None:
        failures.append('Java executable absent or java -version failed; install JDK 17 or newer')
    else:
        version = java_major(java_text)
        if version is None:
            failures.append('Could not determine Java version')
        elif version < 17:
            failures.append(f'Java {version} is too old; use JDK 17 or newer')
    if sdk is None or not sdk.is_dir():
        failures.append('Android SDK missing: set ANDROID_HOME to the installed SDK root')
    else:
        if not (sdk / 'platforms' / f'android-{SDK_API}' / 'android.jar').is_file():
            failures.append(f'Missing Android SDK platform {SDK_API}')
        aapt2 = 'aapt2.exe' if windows else 'aapt2'
        if not (sdk / 'build-tools' / BUILD_TOOLS / aapt2).is_file():
            failures.append(f'Missing Android build-tools {BUILD_TOOLS}')
    if not (project / ('gradlew.bat' if windows else 'gradlew')).is_file():
        failures.append('Missing checked-in Gradle wrapper launcher')
    if not (project / 'gradle' / 'wrapper' / 'gradle-wrapper.jar').is_file():
        failures.append('Missing checked-in gradle-wrapper.jar (never download an unverified replacement)')
    properties = project / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
    if not properties.is_file():
        failures.append('Missing Gradle wrapper properties')
    else:
        contents = properties.read_text(encoding='utf-8')
        if 'gradle-8.9-bin.zip' not in contents or not re.search(r'^distributionSha256Sum=[0-9a-fA-F]{64}$', contents, re.M):
            failures.append('Expected Gradle 8.9 pin + SHA-256 distribution checksum not found')
    return failures


def main() -> int:
    path_text = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    sdk = Path(path_text).expanduser() if path_text else None
    windows = os.name == 'nt'
    suffix = '.exe' if windows else ''
    java_home = os.environ.get('JAVA_HOME')
    java = str(Path(java_home) / 'bin' / f'java{suffix}') if java_home else shutil.which('java')
    version_text = None
    if java:
        try:
            finished = subprocess.run([java, '-version'], capture_output=True, text=True,
                                      timeout=10, check=False)
            if finished.returncode == 0:
                version_text = finished.stderr + finished.stdout
        except (OSError, subprocess.TimeoutExpired):
            pass
    failures = check(PROJECT, sdk, version_text, windows=windows)
    if version_text is not None:
        java_bin = Path(java).resolve().parent
        missing = [tool for tool in ('javac', 'jlink') if not (java_bin / f'{tool}{suffix}').is_file()]
        if missing:
            failures.append(f'Missing JDK tools: {", ".join(missing)}. Set JAVA_HOME to a full JDK 17 or newer.')
    if failures:
        print('BLOCKED: Android build prerequisites')
        for msg in failures:
            print(' -', msg)
        print('No build attempted and no files changed.')
        return 1
    print('PRECHECK PASS: JDK, Android SDK 35/build-tools 35.0.0, and checked-in Gradle wrapper found.')
    print('Next: python tools/ci_free_local.py --android')
    print('This does not prove an APK can build, install, or run.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
