from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass(slots=True)
class Artifact:
    artifact_id: str
    path: str
    root: str
    relative_path: str
    name: str
    suffix: str
    size: int
    sha256: str
    modified_ns: int
    domain: str
    kind: str
    evidence_state: str
    authority: int
    confidence: float
    mapping_reason: str
    symbols: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class Conflict:
    conflict_key: str
    reason: str
    artifact_ids: list[str]
    paths: list[str]
    resolution: str = "retained-for-review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class Need:
    need_id: str
    domain: str
    requirement: str
    status: str
    reason: str
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
