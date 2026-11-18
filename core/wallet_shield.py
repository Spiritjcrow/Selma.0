"""WalletShield v0.1: offline, passive, owner-controlled hardware wallet triage.

This module does NOT scan physical hardware or radios. It evaluates strictly
typed observations supplied by an authorized owner or independent inspector.
No seed phrase, private key, PIN, wallet address, photo, or raw RF capture is
accepted. No network requests, attribution, or automatic reporting occur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
CASE_ID = re.compile(r"[A-Za-z0-9_-]{6,48}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
METHODS = {
    "supply_chain": "documented_receipt",
    "vendor_attestation": "official_vendor_client",
    "physical_inspection": "qualified_inspector",
    "rf_survey": "calibrated_external_receiver",
    "chain_activity": "public_chain_review",
}
RISK_REASONS = {
    "supply_chain": "A supply-chain concern was reported; seller identity is not proof of tampering.",
    "vendor_attestation": "A failed vendor attestation was reported; validate with official vendor support.",
    "physical_inspection": "A suspicious physical modification was reported; independent lab confirmation is required.",
    "rf_survey": "An RF anomaly was reported; unrelated emitters must be ruled out.",
    "chain_activity": "Unexpected chain activity was reported; this is not proof of a hardware implant.",
}
CRITICAL_KINDS = frozenset({"vendor_attestation", "physical_inspection", "rf_survey", "chain_activity"})


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def validate_case(payload: Any) -> dict[str, Any]:
    """Reject unknown or free-text fields, including attempts to supply secrets."""
    if type(payload) is not dict or set(payload) != {"case_id", "observations"}:
        raise ValueError("expected case_id and observations only")
    case_id = payload["case_id"]
    if type(case_id) is not str or not CASE_ID.fullmatch(case_id):
        raise ValueError("case_id must be a 6-48 character pseudonym")
    entries = payload["observations"]
    if type(entries) is not list or len(entries) > 40:
        raise ValueError("observations must be a list of at most 40 items")
    clean = []
    for obs in entries:
        if type(obs) is not dict or not {"kind", "result"} <= set(obs):
            raise ValueError("each observation requires kind and result")
        if set(obs) - {"kind", "result", "method", "evidence_sha256"}:
            raise ValueError("unknown observation field; never submit secrets or raw evidence")
        kind, result = obs["kind"], obs["result"]
        if type(kind) is not str or kind not in METHODS:
            raise ValueError("unsupported observation kind")
        if type(result) is not str or result not in {"pass", "fail", "unknown"}:
            raise ValueError("unsupported observation result")
        method = obs.get("method", "unverified")
        if type(method) is not str or method not in {"unverified", METHODS[kind]}:
            raise ValueError("invalid observation method for kind")
        evidence = obs.get("evidence_sha256")
        if evidence is not None and (type(evidence) is not str or not DIGEST.fullmatch(evidence)):
            raise ValueError("evidence_sha256 must be a lowercase SHA-256 digest")
        clean.append({"kind": kind, "result": result, "method": method, "evidence_sha256": evidence})
    return {"case_id": case_id, "observations": clean}


def assess(payload: Any) -> dict[str, Any]:
    """Triage reports, not prove attacks. An evidence digest does not verify a photo."""
    case = validate_case(payload)
    signals = []
    urgency = 0
    for obs in case["observations"]:
        if obs["result"] != "fail":
            continue
        qualified = (obs["method"] == METHODS[obs["kind"]] and obs["evidence_sha256"] is not None)
        signals.append({
            "kind": obs["kind"],
            "reported_method": obs["method"],
            "evidence_sha256": obs["evidence_sha256"],
            "reason": RISK_REASONS[obs["kind"]],
            "independently_verified": False,
        })
        urgency = max(urgency, 2 if qualified and obs["kind"] in CRITICAL_KINDS else 1)
    level = ("no_reported_indicators", "review", "urgent_review")[urgency]
    advice = [
        "Do not type or upload your recovery phrase into SelmaOS, a website, or support chat.",
        "Use the manufacturer's official software and documented authenticity checks.",
        "If seed exposure is suspected, use a trusted new device to generate a NEW phrase and move funds carefully.",
        "Preserve the device and purchase records; contact the vendor before any disassembly.",
    ]
    return {
        "schema_version": 1,
        "engine": "SelmaSecure/WalletShield",
        "version": VERSION,
        "case_id": case["case_id"],
        "status": level,
        "signals": signals,
        "observations_processed": len(case["observations"]),
        "assessment_basis": "user_supplied_metadata_only; no independent verification",
        "hardware_scanned": False,
        "network_used": False,
        "external_report_sent": False,
        "advice": advice,
    }



def _validate_assessment(assessment: Any) -> None:
    """Allow only deterministic, sanitized assessment fields into local reports."""
    if type(assessment) is not dict:
        raise ValueError("invalid WalletShield assessment")
    baseline = assess({"case_id": "sample_0001", "observations": []})
    expected = set(baseline)
    if set(assessment) != expected:
        raise ValueError("unexpected assessment fields")
    case_id = assessment.get("case_id")
    if type(case_id) is not str or not CASE_ID.fullmatch(case_id):
        raise ValueError("invalid assessment case_id")
    for field in expected - {"case_id", "status", "signals", "observations_processed"}:
        if assessment[field] != baseline[field]:
            raise ValueError("invalid assessment invariant")
    signals = assessment["signals"]
    processed = assessment["observations_processed"]
    if type(signals) is not list or type(processed) is not int or not (0 <= len(signals) <= processed <= 40):
        raise ValueError("invalid assessment observations")
    urgency = 0
    for signal in signals:
        if type(signal) is not dict or set(signal) != {
            "kind", "reported_method", "evidence_sha256", "reason", "independently_verified"
        }:
            raise ValueError("invalid assessment signal fields")
        kind = signal["kind"]
        if type(kind) is not str or kind not in METHODS:
            raise ValueError("invalid assessment signal kind")
        method = signal["reported_method"]
        if type(method) is not str or method not in {"unverified", METHODS[kind]}:
            raise ValueError("invalid assessment method")
        evidence = signal["evidence_sha256"]
        if evidence is not None and (type(evidence) is not str or not DIGEST.fullmatch(evidence)):
            raise ValueError("invalid assessment digest")
        if signal["reason"] != RISK_REASONS[kind] or signal["independently_verified"] is not False:
            raise ValueError("unverified signals may not claim confirmation")
        qualified = (method == METHODS[kind] and evidence is not None)
        urgency = max(urgency, 2 if qualified and kind in CRITICAL_KINDS else 1)
    if assessment["status"] != ("no_reported_indicators", "review", "urgent_review")[urgency]:
        raise ValueError("inconsistent assessment status")


def verify_audit(path: str | Path) -> dict[str, Any]:
    """Verify local hash linkage; not protected against deletion/truncation of the file."""
    path = Path(path)
    if not path.exists():
        return {"valid": True, "entries": 0, "head_sha256": "0" * 64}
    previous = "0" * 64
    number = 0
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                obj = json.loads(line)
                if type(obj) is not dict or set(obj) != {"sequence", "previous_sha256", "assessment", "sha256"}:
                    raise ValueError("invalid audit record")
                material = {key: obj[key] for key in ("sequence", "previous_sha256", "assessment")}
                if obj["sequence"] != number + 1 or obj["previous_sha256"] != previous:
                    raise ValueError("broken audit chain")
                if obj["sha256"] != digest(material):
                    raise ValueError("audit hash mismatch")
                previous = obj["sha256"]
                number += 1
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {"valid": False, "entries_verified": number, "error": type(exc).__name__}
    return {"valid": True, "entries": number, "head_sha256": previous}


def append_audit(path: str | Path, assessment: dict[str, Any]) -> dict[str, Any]:
    """Append one sanitized assessment. Single-writer trusted local directory only."""
    _validate_assessment(assessment)
    path = Path(path)
    status = verify_audit(path)
    if not status["valid"]:
        raise ValueError("refusing to append to a corrupted audit file")
    record = {
        "sequence": status["entries"] + 1,
        "previous_sha256": status["head_sha256"],
        "assessment": assessment,
    }
    record["sha256"] = digest(record)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(canonical(record).decode("utf-8") + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return {"sequence": record["sequence"], "sha256": record["sha256"]}


def export_report(assessment: dict[str, Any], *, owner_approved: bool = False) -> dict[str, Any]:
    """Build a local report only after explicit owner approval; never send it."""
    if owner_approved is not True:
        raise PermissionError("explicit owner approval required for report export")
    _validate_assessment(assessment)
    return {
        "report_version": 1,
        "requires_independent_review": True,
        "no_attribution_or_criminal_finding": True,
        "report_not_transmitted": True,
        "assessment": assessment,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline wallet integrity triage; does not scan hardware")
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("assess")
    check.add_argument("input_json", type=Path)
    check.add_argument("--audit", type=Path, help="append to local single-writer hash log")
    check.add_argument("--export", type=Path, help="write a local report; owner approval required")
    check.add_argument("--owner-approved", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("audit_jsonl", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "verify":
            result = verify_audit(args.audit_jsonl)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 2
        assessment = assess(json.loads(args.input_json.read_text(encoding="utf-8")))
        if args.export:
            report = export_report(assessment, owner_approved=args.owner_approved)
            args.export.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.audit:
            append_audit(args.audit, assessment)
        print(json.dumps(assessment, indent=2))
        return 0
    except (ValueError, PermissionError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"walletshield: {type(exc).__name__}; request not processed\n")


if __name__ == "__main__":
    raise SystemExit(main())
