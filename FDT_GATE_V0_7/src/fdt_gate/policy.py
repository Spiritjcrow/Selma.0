from __future__ import annotations

import fnmatch
import shlex

from .canonical import canonical_json, ir_build_id, sha256_hex
from .crypto import Keyring, Signer
from .models import Decision, PolicyBundle, PolicyRule, Risk


def parse_policy(source: str) -> tuple[str, str, Decision, tuple[PolicyRule, ...]]:
    policy_id = ""
    version = "0.7.0"
    default = Decision.DENY
    rules: list[PolicyRule] = []
    seen: set[str] = set()

    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = shlex.split(line, comments=True, posix=True)
        if not parts:
            continue
        head = parts[0]
        if head == "fdt-policy":
            if len(parts) != 2 or parts[1] != "0.7":
                raise ValueError(f"line {lineno}: expected 'fdt-policy 0.7'")
        elif head == "policy":
            if len(parts) != 2:
                raise ValueError(f"line {lineno}: policy requires one id")
            policy_id = parts[1]
        elif head == "version":
            if len(parts) != 2:
                raise ValueError(f"line {lineno}: version requires one value")
            version = parts[1]
        elif head == "default":
            if len(parts) != 2:
                raise ValueError(f"line {lineno}: default requires one decision")
            default = Decision(parts[1])
        elif head == "rule":
            if len(parts) < 2:
                raise ValueError(f"line {lineno}: missing rule id")
            rid = parts[1]
            if rid in seen:
                raise ValueError(f"line {lineno}: duplicate rule id {rid}")
            seen.add(rid)
            kv: dict[str, str] = {}
            for item in parts[2:]:
                if "=" not in item:
                    raise ValueError(f"line {lineno}: expected key=value, got {item}")
                k, v = item.split("=", 1)
                if k in kv:
                    raise ValueError(f"line {lineno}: duplicate key {k}")
                kv[k] = v
            required = {"effect", "resource", "capability", "decision"}
            missing = required - kv.keys()
            if missing:
                raise ValueError(f"line {lineno}: missing {sorted(missing)}")
            unknown = set(kv) - {
                "effect", "resource", "capability", "decision", "risk", "methods",
                "max_payload_bytes", "max_calls_per_minute",
            }
            if unknown:
                raise ValueError(f"line {lineno}: unknown keys {sorted(unknown)}")
            max_payload_bytes = int(kv.get("max_payload_bytes", "65536"))
            max_calls_per_minute = int(kv.get("max_calls_per_minute", "60"))
            if max_payload_bytes < 0 or max_calls_per_minute < 1:
                raise ValueError(f"line {lineno}: invalid resource budget")
            rules.append(PolicyRule(
                rule_id=rid,
                effect=kv["effect"],
                resource=kv["resource"],
                capability=kv["capability"],
                decision=Decision(kv["decision"]),
                risk=Risk(kv.get("risk", "LOW")),
                methods=tuple(x for x in kv.get("methods", "*").split(",") if x),
                max_payload_bytes=max_payload_bytes,
                max_calls_per_minute=max_calls_per_minute,
            ))
        else:
            raise ValueError(f"line {lineno}: unknown statement {head}")
    if not policy_id:
        raise ValueError("policy id is required")
    return policy_id, version, default, tuple(rules)


def compile_policy(source: str, signer: Signer) -> PolicyBundle:
    policy_id, version, default, rules = parse_policy(source)
    ir = {
        "schema_version": "fdt.policy.v1",
        "policy_id": policy_id,
        "policy_version": version,
        "default_decision": default.value,
        "rules": [r.to_dict() for r in rules],
    }
    build_id = ir_build_id(ir)
    unsigned = {
        **ir,
        "build_id": build_id,
        "source_hash": "sha256:" + sha256_hex(source.encode("utf-8")),
        "signer_key_id": signer.key_id,
    }
    signature = signer.sign(canonical_json(unsigned))
    return PolicyBundle(
        policy_id=policy_id, policy_version=version, default_decision=default,
        rules=rules, build_id=build_id, source_hash=unsigned["source_hash"],
        signer_key_id=signer.key_id, signature=signature,
    )


def verify_policy(bundle: PolicyBundle, keyring: Keyring) -> bool:
    ir = {
        "schema_version": bundle.schema_version,
        "policy_id": bundle.policy_id,
        "policy_version": bundle.policy_version,
        "default_decision": bundle.default_decision.value,
        "rules": [r.to_dict() for r in bundle.rules],
    }
    if ir_build_id(ir) != bundle.build_id:
        return False
    return keyring.verify(bundle.signer_key_id, canonical_json(bundle.unsigned_dict()), bundle.signature)


def match_rule(bundle: PolicyBundle, effect: str, resource: str, method: str) -> PolicyRule | None:
    for rule in bundle.rules:
        if rule.effect != effect:
            continue
        if not fnmatch.fnmatchcase(resource, rule.resource):
            continue
        if "*" not in rule.methods and method not in rule.methods:
            continue
        return rule
    return None
