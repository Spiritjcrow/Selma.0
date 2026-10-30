#!/usr/bin/env python3
"""Static-only review of Selma Candidate Forge diff: no candidate code execution."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from tools import selma_candidate_forge as forge

ROOT = Path(__file__).resolve().parent.parent
ID_PATTERN = re.compile(r'^\d{8}T\d{6}Z-[a-f0-9]{12}$')
HEX_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def review(root, candidate_id):
    if not ID_PATTERN.fullmatch(candidate_id):
        raise forge.ForgeError('invalid candidate identifier')
    if forge.git_private(root, 'SELMA_BUILD_STOP').exists():
        raise forge.ForgeError('kill switch set')
    checkout_sha = forge.clean_head(root)
    folder = forge.git_private(root, 'selma-forge')
    prefix = folder / candidate_id
    manifest_path = prefix.with_suffix('.json')
    patch_path = prefix.with_suffix('.diff')
    if manifest_path.is_symlink() or patch_path.is_symlink():
        raise forge.ForgeError('symlinked candidate evidence rejected')
    if not manifest_path.is_file() or not patch_path.is_file():
        raise forge.ForgeError('candidate evidence missing')
    manifest_bytes = manifest_path.read_bytes()
    patch_bytes = patch_path.read_bytes()
    if len(manifest_bytes) > 8192 or len(patch_bytes) > 150_000:
        raise forge.ForgeError('candidate evidence oversized')
    manifest = forge.decode_json(manifest_bytes)
    expected = {'candidate_id', 'base_sha', 'target', 'goal', 'model',
                'old_sha256', 'candidate_sha256', 'status', 'created_utc'}
    if not isinstance(manifest, dict) or set(manifest) != expected:
        raise forge.ForgeError('malformed candidate manifest')
    if manifest['candidate_id'] != candidate_id or manifest['base_sha'] != checkout_sha:
        raise forge.ForgeError('mismatched candidate identity or base revision')
    if manifest['status'] != 'REVIEW_ONLY_NOT_EXECUTED':
        raise forge.ForgeError('unexpected candidate status')
    if not all(isinstance(manifest[k], str) and HEX_SHA256.fullmatch(manifest[k])
               for k in ('old_sha256', 'candidate_sha256')):
        raise forge.ForgeError('invalid content hashes')
    target = forge.validate_target(root, manifest['target'])
    original = target.read_bytes()
    if digest(original) != manifest['old_sha256']:
        raise forge.ForgeError('source hash drift')
    patch = patch_bytes.decode('utf-8')
    source_name = manifest['target']
    headers = [line for line in patch.splitlines() if line.startswith(('--- ', '+++ '))]
    if headers != ['--- a/' + source_name, '+++ b/' + source_name]:
        raise forge.ForgeError('unexpected patch headers / multiple files')
    if 'GIT binary patch' in patch or '\x00' in patch:
        raise forge.ForgeError('binary patches rejected')
    with tempfile.TemporaryDirectory(prefix='selma-static-review-') as temp:
        root_copy = Path(temp)
        path_copy = root_copy / source_name
        path_copy.parent.mkdir(parents=True)
        path_copy.write_bytes(original)
        command = ['git', 'apply', '--check', '--', str(patch_path)]
        try:
            subprocess.run(command, cwd=root_copy, check=True,
                           capture_output=True, text=True, timeout=10)
            subprocess.run(['git', 'apply', '--', str(patch_path)], cwd=root_copy,
                           check=True, capture_output=True, text=True, timeout=10)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise forge.ForgeError('patch cannot apply cleanly') from error
        if not path_copy.is_file() or path_copy.is_symlink():
            raise forge.ForgeError('candidate target was removed')
        replacement = path_copy.read_bytes()
        other_files = [p for p in root_copy.rglob('*') if p.is_file() and p != path_copy]
        if other_files:
            raise forge.ForgeError('patch attempted extra file writes')
        if digest(replacement) != manifest['candidate_sha256']:
            raise forge.ForgeError('candidate content digest mismatch')
        parsed = False
        if target.suffix == '.py':
            try:
                ast.parse(replacement.decode('utf-8'), filename=source_name)
            except (SyntaxError, UnicodeError) as error:
                raise forge.ForgeError('Python candidate syntax invalid') from error
            parsed = True
    if forge.git_private(root, 'SELMA_BUILD_STOP').exists() or forge.clean_head(root) != checkout_sha:
        raise forge.ForgeError('source changed or stop switch set during review')
    report = {'candidate_id': candidate_id, 'base_sha': checkout_sha, 'target': source_name,
              'sha256': digest(replacement), 'patch_sha256': digest(patch_bytes),
              'applies_cleanly': True, 'python_ast_parse_passed': parsed,
              'status': 'STATIC_OK_HUMAN_REVIEW_REQUIRED', 'tests_executed': False}
    report_file = prefix.with_suffix('.review.json')
    forge.atomic_write(report_file, json.dumps(report, indent=2) + '\n')
    return report_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-id', required=True)
    args = parser.parse_args()
    try:
        path = review(ROOT, args.candidate_id)
        print(f'Static-only review recorded: {path}')
        print('NO generated code executed; tests/merge/deployment NOT_RUN.')
        return 0
    except (forge.ForgeError, OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        print(f'FAIL CLOSED: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
