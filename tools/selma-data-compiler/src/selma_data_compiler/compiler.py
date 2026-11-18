from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from .scanner import scan_roots
from .merge import canonical_rank, exact_duplicate_groups, find_conflicts
from .needs import build_dependency_map, infer_needs
from .catalog import write_catalog

class SelmaDataCompiler:
    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir

    def compile(self, roots: Iterable[str | Path]) -> dict:
        roots = [Path(r).expanduser() for r in roots]
        if not roots:
            raise ValueError("At least one root is required.")
        artifacts = canonical_rank(scan_roots(roots))
        duplicates = exact_duplicate_groups(artifacts)
        conflicts = find_conflicts(artifacts)
        depmap = build_dependency_map(artifacts)
        needs = infer_needs(artifacts, depmap)
        out = self.output_dir
        if out is None:
            first = roots[0].resolve()
            base = first if first.is_dir() else first.parent
            out = base / ".selma" / "compiler"
        out.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "compiler": "selma-data-compiler",
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "roots": [str(r.resolve()) for r in roots if r.exists()],
            "counts": {"artifacts": len(artifacts), "duplicates": sum(len(v)-1 for v in duplicates.values()), "duplicate_groups": len(duplicates), "conflicts": len(conflicts), "needs": len(needs)},
            "domains": dict(sorted(Counter(a.domain for a in artifacts).items())),
            "artifacts": [a.to_dict() for a in artifacts],
            "duplicates": {h: [a.artifact_id for a in group] for h, group in sorted(duplicates.items())},
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (out / "dependency_map.json").write_text(json.dumps(depmap, indent=2), encoding="utf-8")
        (out / "conflicts.json").write_text(json.dumps([c.to_dict() for c in conflicts], indent=2), encoding="utf-8")
        (out / "needs.json").write_text(json.dumps([n.to_dict() for n in needs], indent=2), encoding="utf-8")
        write_catalog(out / "catalog.sqlite3", artifacts, conflicts, needs)
        return {"output_dir": str(out), "manifest": manifest, "dependency_map": depmap, "conflicts": [c.to_dict() for c in conflicts], "needs": [n.to_dict() for n in needs]}
