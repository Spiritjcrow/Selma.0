from __future__ import annotations
from collections import defaultdict
from pathlib import PurePath
from .model import Artifact, Conflict

def exact_duplicate_groups(artifacts: list[Artifact]) -> dict[str, list[Artifact]]:
    by_hash = defaultdict(list)
    for a in artifacts: by_hash[a.sha256].append(a)
    return {h: g for h, g in by_hash.items() if len(g) > 1}

def _logical_key(a: Artifact) -> str:
    return f"{a.domain}:{PurePath(a.name).stem.lower().replace('-', '_')}:{a.kind}"

def find_conflicts(artifacts: list[Artifact]) -> list[Conflict]:
    groups = defaultdict(list)
    for a in artifacts: groups[_logical_key(a)].append(a)
    conflicts = []
    for key, group in groups.items():
        if len(group) < 2 or len({a.sha256 for a in group}) < 2: continue
        ordered = sorted(group, key=lambda a: (-a.authority, -a.modified_ns, -a.confidence))
        conflicts.append(Conflict(key, "same-logical-role-different-content", [a.artifact_id for a in ordered], [a.path for a in ordered], "ranked-but-retained"))
    return conflicts

def canonical_rank(artifacts: list[Artifact]) -> list[Artifact]:
    return sorted(artifacts, key=lambda a: (a.domain, -a.authority, -a.confidence, -a.modified_ns, a.relative_path.lower()))
