#!/usr/bin/env python3
"""Generate the evidence-based OS support matrix from adapter manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "adapters" / "manifests"
OUTPUT = ROOT / "docs" / "architecture" / "OS_SUPPORT_MATRIX.md"
ARCHITECTURE_MANIFEST = ROOT / "docs" / "architecture" / "architecture-manifest.v1.json"
ALLOWED_STATES = {"implemented", "tested", "unavailable", "planned"}
ALLOWED_RISK_CLASSES = {"read", "sensitive_read", "approved_write"}
SCHEMA_VERSION = 1


def load_json(path: Path) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    with path.open(encoding="utf-8") as handle:
        value = json.load(handle, object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def validate_architecture(architecture: dict[str, Any]) -> list[str]:
    if architecture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"architecture schema_version must be {SCHEMA_VERSION}")
    require_text(architecture.get("architecture_version"), "architecture_version")
    if set(architecture.get("support_states", [])) != ALLOWED_STATES:
        raise ValueError("architecture support_states do not match generator states")
    if set(architecture.get("risk_classes", [])) != ALLOWED_RISK_CLASSES:
        raise ValueError("architecture risk_classes do not match generator risk classes")

    raw_capabilities = architecture.get("capabilities")
    if not isinstance(raw_capabilities, list) or not raw_capabilities:
        raise ValueError("architecture capabilities must be a non-empty list")
    capabilities: list[str] = []
    for index, item in enumerate(raw_capabilities):
        field = f"architecture.capabilities[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{field} must be an object")
        capability = require_text(item.get("id"), f"{field}.id")
        require_text(item.get("label"), f"{field}.label")
        require_text(item.get("protocol"), f"{field}.protocol")
        if item.get("risk_floor") not in ALLOWED_RISK_CLASSES:
            raise ValueError(f"{field}.risk_floor is invalid")
        mutation_risk = item.get("mutation_risk")
        if mutation_risk is not None and mutation_risk not in ALLOWED_RISK_CLASSES:
            raise ValueError(f"{field}.mutation_risk is invalid")
        if capability in capabilities:
            raise ValueError(f"duplicate architecture capability: {capability}")
        capabilities.append(capability)

    manifest_contract = architecture.get("adapter_manifests")
    if not isinstance(manifest_contract, dict):
        raise ValueError("architecture adapter_manifests must be an object")
    if manifest_contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"adapter manifest schema_version must be {SCHEMA_VERSION}")
    if manifest_contract.get("required_capability_coverage") != "all":
        raise ValueError("adapter manifests must require all capability coverage")
    return capabilities


def validate_manifest(
    manifest: dict[str, Any],
    capabilities: list[str],
    *,
    source: Path | str,
) -> None:
    label = str(source)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{label}: schema_version must be {SCHEMA_VERSION}")
    platform_id = require_text(manifest.get("platform_id"), f"{label}.platform_id")
    require_text(manifest.get("platform"), f"{label}.platform")
    require_text(manifest.get("adapter_version"), f"{label}.adapter_version")
    require_text(manifest.get("evidence_scope"), f"{label}.evidence_scope")
    display_order = manifest.get("display_order")
    if isinstance(display_order, bool) or not isinstance(display_order, int):
        raise ValueError(f"{label}.display_order must be an integer")
    if isinstance(source, Path) and source.name != f"{platform_id}.v1.json":
        raise ValueError(f"{label}: filename does not match platform_id {platform_id!r}")

    entries = manifest.get("capabilities")
    if not isinstance(entries, dict) or set(entries) != set(capabilities):
        raise ValueError(f"{platform_id}: capability coverage differs from architecture manifest")
    for capability, record in entries.items():
        if not isinstance(record, dict) or set(record) != {"state", "evidence"}:
            raise ValueError(f"{platform_id}.{capability}: expected state and evidence")
        if record["state"] not in ALLOWED_STATES:
            raise ValueError(
                f"{platform_id}.{capability}: invalid state {record['state']!r}"
            )
        require_text(record["evidence"], f"{platform_id}.{capability}.evidence")


def load_inputs() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    architecture = load_json(ARCHITECTURE_MANIFEST)
    capabilities = validate_architecture(architecture)
    manifest_paths = sorted(MANIFEST_DIR.glob("*.json"))
    manifests = [load_json(path) for path in manifest_paths]
    if not manifests:
        raise ValueError("no adapter manifests found")
    seen: set[str] = set()
    for path, manifest in zip(manifest_paths, manifests, strict=True):
        validate_manifest(manifest, capabilities, source=path)
        platform_id = manifest["platform_id"]
        if platform_id in seen:
            raise ValueError(f"duplicate platform_id: {platform_id}")
        seen.add(platform_id)
    manifests.sort(key=lambda item: (item.get("display_order", 999), item["platform_id"]))
    return architecture, manifests


def render_matrix() -> str:
    architecture, manifests = load_inputs()
    capabilities = [item["id"] for item in architecture["capabilities"]]
    labels = {item["id"]: item["label"] for item in architecture["capabilities"]}
    lines = [
        "<!-- Generated by tools/generate_support_matrix.py; do not edit manually. -->",
        "# SelmaOS support matrix",
        "",
        f"Architecture contract: `{architecture['architecture_version']}`. "
        f"Evidence baseline: `{architecture['evidence_baseline']['commit']}`.",
        "",
        "Status describes repository evidence, not a marketing claim or physical-device result.",
        "",
        "| Platform | " + " | ".join(labels[item] for item in capabilities) + " |",
        "|---|" + "---|" * len(capabilities),
    ]
    for manifest in manifests:
        row = [manifest["platform"]]
        row.extend(manifest["capabilities"][item]["state"] for item in capabilities)
        lines.append("| " + " | ".join(row) + " |")
    lines.extend(
        [
            "",
            "## Legend",
            "",
            "- **implemented** - source exists on the evidence baseline, but all target "
            "acceptance gates are not complete.",
            "- **tested** - the cited automated test scope passed; owned-device evidence "
            "is separate unless explicitly cited.",
            "- **unavailable** - the adapter deliberately fails closed or the platform "
            "does not expose the required public API.",
            "- **planned** - specified work has no implementation on the evidence baseline.",
            "",
            "## Evidence and limitations",
            "",
        ]
    )
    for manifest in manifests:
        lines.append(f"### {manifest['platform']}")
        lines.append("")
        lines.append(f"Evidence scope: {manifest['evidence_scope']}")
        lines.append("")
        for capability in capabilities:
            record = manifest["capabilities"][capability]
            lines.append(f"- **{labels[capability]} ({record['state']}):** {record['evidence']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when the generated file is stale")
    args = parser.parse_args()
    rendered = render_matrix()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            raise SystemExit(f"{OUTPUT.relative_to(ROOT)} is stale; regenerate it")
        print(f"{OUTPUT.relative_to(ROOT)} is current")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
