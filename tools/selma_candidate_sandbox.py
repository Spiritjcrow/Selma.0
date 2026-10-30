#!/usr/bin/env python3
"""Run reviewed Selma candidate in disposable, offline, unprivileged Docker container.

Requires an owner-preloaded, pinned Python image digest and Docker Linux daemon.
Never uses a Docker socket mount, host secrets, remote image pull, or auto-merge.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

from tools import selma_candidate_forge as forge
from tools import selma_candidate_review as review

ROOT = Path(__file__).resolve().parent.parent
IMAGE_REGEX = re.compile(r'^python@sha256:[0-9a-f]{64}$')


def build_command(image, source, container_name):
    if not isinstance(image, str) or not IMAGE_REGEX.fullmatch(image):
        raise forge.ForgeError('image must be a pinned python@sha256 digest')
    if not source.is_dir() or source.is_symlink():
        raise forge.ForgeError('candidate snapshot not a regular directory')
    return ['docker', 'run', '--rm', '--pull', 'never', '--name', container_name,
            '--network', 'none', '--read-only', '--user', '65534:65534',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--pids-limit', '64', '--memory', '512m', '--cpus', '1',
            '--tmpfs', '/tmp:rw,nosuid,noexec,size=128m',
            '--mount', f'type=bind,src={source.resolve()},dst=/src,readonly',
            '--workdir', '/src', image, 'python', '-B', '-m', 'unittest',
            'discover', '-s', 'tests', '-p', 'test_*.py', '-q']


def read_evidence(root, candidate_id):
    if not review.ID_PATTERN.fullmatch(candidate_id):
        raise forge.ForgeError('invalid candidate id')
    head = forge.clean_head(root)
    directory = forge.git_private(root, 'selma-forge')
    prefix = directory / candidate_id
    manifest_file = prefix.with_suffix('.json')
    patch_file = prefix.with_suffix('.diff')
    report_file = prefix.with_suffix('.review.json')
    if any(p.is_symlink() or not p.is_file() for p in (manifest_file, patch_file, report_file)):
        raise forge.ForgeError('missing reviewed candidate evidence')
    manifest = forge.decode_json(manifest_file.read_bytes())
    report = forge.decode_json(report_file.read_bytes())
    if not isinstance(manifest, dict) or not isinstance(report, dict):
        raise forge.ForgeError('invalid candidate evidence')
    if (manifest.get('candidate_id') != candidate_id or manifest.get('base_sha') != head
            or report.get('candidate_id') != candidate_id or report.get('base_sha') != head
            or report.get('status') != 'STATIC_OK_HUMAN_REVIEW_REQUIRED'
            or report.get('tests_executed') is not False):
        raise forge.ForgeError('static review was not verified for this source revision')
    target = manifest.get('target')
    if report.get('target') != target or not isinstance(target, str):
        raise forge.ForgeError('target mismatch')
    original = forge.validate_target(root, target).read_bytes()
    diff = patch_file.read_bytes()
    if (len(diff) > 150_000 or hashlib.sha256(diff).hexdigest() != report.get('patch_sha256')
            or hashlib.sha256(original).hexdigest() != manifest.get('old_sha256')):
        raise forge.ForgeError('candidate integrity mismatch')
    headers = [line for line in diff.decode('utf-8').splitlines()
               if line.startswith(('--- ', '+++ '))]
    if headers != ['--- a/' + target, '+++ b/' + target]:
        raise forge.ForgeError('candidate diff scope mismatch')
    return head, target, diff, manifest['candidate_sha256']


def snapshot_candidate(root, target, patch, expected_digest, output):
    # Archive exact committed code; never copy .git, untracked files, or secrets outside Git.
    archive = subprocess.run(['git', 'archive', '--format=tar', 'HEAD'], cwd=root,
                             capture_output=True, check=True, timeout=60).stdout
    if len(archive) > 20_000_000:
        raise forge.ForgeError('repository archive too large for bounded candidate runner')
    output.mkdir(mode=0o755)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(output, filter='data')  # Python >= 3.12 path/symlink protections
    copy = output / target
    if not copy.is_file() or copy.is_symlink():
        raise forge.ForgeError('candidate target missing from committed archive')
    patch_file = output.parent / 'candidate.diff'
    patch_file.write_bytes(patch)
    try:
        subprocess.run(['git', 'apply', '--check', '--', str(patch_file)], cwd=output,
                       check=True, capture_output=True, timeout=15)
        subprocess.run(['git', 'apply', '--', str(patch_file)], cwd=output,
                       check=True, capture_output=True, timeout=15)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise forge.ForgeError('candidate cannot be applied in isolated snapshot') from error
    after = copy.read_bytes()
    if hashlib.sha256(after).hexdigest() != expected_digest:
        raise forge.ForgeError('isolated snapshot candidate digest mismatch')
    if copy.suffix == '.py':
        try:
            ast.parse(after.decode('utf-8'), filename=target)
        except (SyntaxError, UnicodeError) as error:
            raise forge.ForgeError('snapshot candidate syntax invalid') from error


def run_bounded(command, stop_file, container_name, deadline):
    proc = subprocess.Popen(command)
    try:
        while proc.poll() is None:
            if stop_file.exists():
                return 130
            if time.monotonic() >= deadline:
                return 124
            time.sleep(0.5)
        # A stop request racing with CLI completion must not report PASS.
        if stop_file.exists():
            return 130
        return proc.returncode
    finally:
        # Docker CLI exits and detached containers can outlive the CLI; clean by exact random name.
        cleanup_error = None
        try:
            # --rm may already have removed the container; rm's nonzero exit alone
            # cannot distinguish that normal race from a daemon/cleanup failure.
            subprocess.run(['docker', 'rm', '-f', container_name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15, check=False)
            # Confirm absence using the same Docker context; never infer it from
            # a failed rm or a CLI process that exited successfully.
            verified = subprocess.run(
                ['docker', 'ps', '-a', '--filter', f'name=^/{container_name}$',
                 '--format', '{{.Names}}'],
                capture_output=True, text=True, timeout=15, check=False)
            if (verified.returncode != 0 or not isinstance(verified.stdout, str)
                    or verified.stdout.strip()):
                cleanup_error = forge.ForgeError('Docker container absence not verified')
        except (OSError, subprocess.SubprocessError) as error:
            cleanup_error = error
        finally:
            # Always reap the local Docker CLI, including when docker rm times out.
            if proc.poll() is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    # Docker CLI exited between poll() and terminate().
                    pass
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        # Docker CLI exited between wait() timeout and kill().
                        pass
                    proc.wait(timeout=3)
        if cleanup_error is not None:
            raise forge.ForgeError('Docker cleanup unverified') from cleanup_error


def run(root, candidate_id, image, *, timeout_seconds=300):
    if not 30 <= timeout_seconds <= 600:
        raise forge.ForgeError('timeout must be 30..600 seconds')
    if not IMAGE_REGEX.fullmatch(image):
        raise forge.ForgeError('untrusted or unpinned container image')
    stop = forge.git_private(root, 'SELMA_BUILD_STOP')
    if stop.exists():
        raise forge.ForgeError('kill switch set')
    head, target, patch, digest = read_evidence(root, candidate_id)
    if not shutil.which('docker'):
        raise forge.ForgeError('Docker Linux container runner unavailable')
    inspect = subprocess.run(['docker', 'image', 'inspect', image],
                             capture_output=True, timeout=15, check=False)
    if inspect.returncode:
        raise forge.ForgeError('pinned container image not preloaded; no auto-pull')
    name = 'selma-candidate-' + uuid.uuid4().hex[:14]
    with tempfile.TemporaryDirectory(prefix='selma-container-candidate-') as tmp:
        source = Path(tmp) / 'source'
        snapshot_candidate(root, target, patch, digest, source)
        if forge.clean_head(root) != head or stop.exists():
            raise forge.ForgeError('source changed before Docker execution')
        command = build_command(image, source, name)
        code = run_bounded(command, stop, name, time.monotonic() + timeout_seconds)
    if stop.exists():
        raise forge.ForgeError('kill switch set during Docker execution')
    if forge.clean_head(root) != head:
        raise forge.ForgeError('source revision changed during Docker execution')
    prefix = forge.git_private(root, 'selma-forge') / candidate_id
    evidence = {'candidate_id': candidate_id, 'base_sha': head, 'image': image,
                'return_code': code, 'network': 'none', 'unprivileged': True,
                'status': 'ISOLATED_TEST_PASS_REVIEW_REQUIRED' if code == 0 else 'ISOLATED_TEST_FAILED',
                'release_authorized': False}
    forge.atomic_write(prefix.with_suffix('.sandbox.json'), json.dumps(evidence, indent=2) + '\n')
    return code


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate-id', required=True)
    ap.add_argument('--image', required=True, help='preloaded python@sha256:<64 hex> digest')
    ap.add_argument('--timeout-seconds', type=int, default=300)
    args = ap.parse_args()
    try:
        code = run(ROOT, args.candidate_id, args.image, timeout_seconds=args.timeout_seconds)
        print(f'Isolated Docker test exit code {code}; human review still required.')
        return code
    except (forge.ForgeError, OSError, ValueError, UnicodeError, subprocess.SubprocessError, tarfile.TarError) as e:
        print(f'FAIL CLOSED: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
