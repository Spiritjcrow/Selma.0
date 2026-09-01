#!/usr/bin/env python3
"""Dependency-free policy validator for Selma personification records."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

STATES = {"IDLE", "LISTENING", "THINKING", "SPEAKING", "INTERRUPTED", "SLEEPING", "ERROR"}
FORBIDDEN_KEYS = {"secret", "password", "token", "private_conversation", "medical_data", "biometric_template", "training_data"}

def validate(record: dict, mapping: dict) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "personification_id", "record_version", "compatibility", "classification", "provenance", "consent", "localization", "behavior", "expression_contract", "quality"}
    missing = sorted(required - record.keys())
    if missing: errors.append(f"missing required keys: {', '.join(missing)}")
    if record.get("schema_version") != "1.0.0": errors.append("unsupported schema_version")
    if not str(record.get("personification_id", "")).startswith("personification:"): errors.append("unstable personification_id")
    classes = record.get("classification", {})
    for name in ("biography", "authored_design", "inferred_preferences", "synthetic_material"):
        if name not in classes: errors.append(f"classification.{name} must be explicit")
    if classes.get("identity_basis") == "authorized-subject":
        consent = record.get("consent", {})
        if consent.get("likeness_status") != "documented-authorization" or consent.get("voice_status") != "documented-authorization":
            errors.append("authorized subjects require documented likeness and voice authorization")
    sources = {s.get("source_id"): s for s in record.get("provenance", [])}
    if None in sources: errors.append("provenance source_id missing")
    for group in ("biography", "authored_design", "inferred_preferences", "synthetic_material"):
        for item in classes.get(group, []):
            if item.get("source_id") not in sources: errors.append(f"unknown source_id in {group}")
        if group == "inferred_preferences":
            for item in classes.get(group, []):
                if not 0 <= item.get("confidence", -1) <= 1: errors.append("inference confidence must be 0..1")
    lowered = json.dumps(record, sort_keys=True).lower()
    for key in FORBIDDEN_KEYS:
        if f'"{key}"' in lowered: errors.append(f"forbidden dataset field: {key}")
    states = set(record.get("expression_contract", {}).get("states", []))
    if states != STATES: errors.append("expression states must exactly match the v1 contract")
    mapped = set(mapping.get("states", {}))
    if not states.issubset(mapped): errors.append("renderer mapping does not cover every state")
    if mapping.get("contract") != record.get("compatibility", {}).get("contract"): errors.append("renderer contract mismatch")
    return sorted(set(errors))

def canonical_digest(record: dict) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("mapping", type=Path)
    args = parser.parse_args()
    record, mapping = json.loads(args.record.read_text()), json.loads(args.mapping.read_text())
    errors = validate(record, mapping)
    if errors:
        print("INVALID\n" + "\n".join(f"- {e}" for e in errors)); return 1
    print(f"VALID sha256:{canonical_digest(record)}"); return 0

if __name__ == "__main__": raise SystemExit(main())
