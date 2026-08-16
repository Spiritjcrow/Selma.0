from __future__ import annotations
import hashlib
from collections import defaultdict
from .model import Artifact, Need
from .rules import DOMAIN_DEPENDENCIES

def build_dependency_map(artifacts: list[Artifact]) -> dict:
    by_domain = defaultdict(list)
    for a in artifacts: by_domain[a.domain].append(a)
    domains = sorted(by_domain)
    edges = []
    for domain in domains:
        for dep in DOMAIN_DEPENDENCIES.get(domain, ()):
            edges.append({"from": domain, "to": dep, "status": "present" if dep in by_domain else "missing", "reason": "domain-integration-rule"})
    refs = [{"artifact_id": a.artifact_id, "from": a.relative_path, "reference": ref} for a in artifacts for ref in a.references]
    return {
        "domains": {d: {"artifact_count": len(items), "source_present": sum(a.evidence_state == "source-present" for a in items), "partial_or_placeholder": sum(a.evidence_state == "placeholder-or-partial" for a in items), "planned": sum(a.evidence_state == "planned" for a in items)} for d, items in sorted(by_domain.items())},
        "domain_edges": edges,
        "file_references": refs,
    }

def infer_needs(artifacts: list[Artifact], dependency_map: dict) -> list[Need]:
    needs = []
    for edge in dependency_map["domain_edges"]:
        if edge["status"] == "missing":
            raw = f'{edge["from"]}->{edge["to"]}'
            needs.append(Need(hashlib.sha256(raw.encode()).hexdigest()[:16], edge["from"], edge["to"], "missing-integration-domain", f'{edge["from"]} has a canonical integration dependency on {edge["to"]}.', []))
    for domain, info in dependency_map["domains"].items():
        if info["artifact_count"] and info["source_present"] == 0:
            raw = f"{domain}:no-source-present"
            needs.append(Need(hashlib.sha256(raw.encode()).hexdigest()[:16], domain, "source-present implementation evidence", "planning-or-placeholder-only", "Artifacts exist, but the compiler did not find source-present evidence in this domain.", []))
    return needs
