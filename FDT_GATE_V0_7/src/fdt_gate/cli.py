from __future__ import annotations

import argparse
import json
import secrets
import tempfile
from datetime import timedelta
from pathlib import Path

from .adapters import AdapterRegistry, FilesystemAdapter
from .audit import AuditLedger
from .canonical import fmt_time, utc_now
from .crypto import Keyring, Signer
from .gate import FDTGate
from .models import ActionEnvelope, PolicyBundle
from .policy import compile_policy
from .security import WingDingynouse, issue_approval, issue_grant
from .server import TokenPrincipalMap, serve
from .store import SecurityStore


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")


def init_workspace(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    keys = root / "keys"
    genesis = Signer.generate()
    runtime = Signer.generate()
    genesis.save_private(keys / "genesis.pem")
    runtime.save_private(keys / "runtime.pem")
    (keys / "genesis.pub.pem").write_text(genesis.public_pem(), "ascii")
    (keys / "runtime.pub.pem").write_text(runtime.public_pem(), "ascii")

    source = """fdt-policy 0.7
policy local-development
version 0.7.0
default DENY
rule read-workspace effect=fs.read resource=workspace/** capability=workspace.read decision=ALLOW risk=LOW methods=READ max_payload_bytes=4096 max_calls_per_minute=120
rule write-workspace effect=fs.write resource=workspace/** capability=workspace.write decision=REQUIRE_APPROVAL risk=HIGH methods=WRITE max_payload_bytes=65536 max_calls_per_minute=30
"""
    (root / "policy.fdt").write_text(source, "utf-8")
    bundle = compile_policy(source, genesis)
    _write_json(root / "policy.bundle.json", bundle.to_dict())

    now = utc_now()
    store = SecurityStore(root / "state.sqlite3")
    store.put_grant(issue_grant(
        signer=genesis, issuer="genesis", subject="local-agent", capability="workspace.read",
        resource_prefix="workspace/", effects=("fs.read",), methods=("READ",),
        not_before=fmt_time(now - timedelta(minutes=1)), expires_at=fmt_time(now + timedelta(days=30)),
        issued_at=fmt_time(now),
    ))
    store.put_grant(issue_grant(
        signer=genesis, issuer="genesis", subject="local-agent", capability="workspace.write",
        resource_prefix="workspace/", effects=("fs.write",), methods=("WRITE",),
        not_before=fmt_time(now - timedelta(minutes=1)), expires_at=fmt_time(now + timedelta(days=30)),
        issued_at=fmt_time(now),
    ))

    token = secrets.token_urlsafe(32)
    _write_json(root / "tokens.json", {TokenPrincipalMap.digest(token): "local-agent"})
    (root / "workspace").mkdir(exist_ok=True)
    return {"root": str(root), "principal": "local-agent", "bearer_token": token,
            "genesis_key_id": genesis.key_id, "runtime_key_id": runtime.key_id}


def load_gate(root: Path) -> tuple[FDTGate, TokenPrincipalMap, SecurityStore, str]:
    # Runtime verification loads only Genesis PUBLIC material; root private key stays cold.
    runtime = Signer.load(root / "keys/runtime.pem")
    keys = Keyring()
    genesis_key_id = keys.add_pem((root / "keys/genesis.pub.pem").read_text("ascii"))
    keys.add_signer(runtime)
    bundle = PolicyBundle.from_dict(json.loads((root / "policy.bundle.json").read_text("utf-8")))
    store = SecurityStore(root / "state.sqlite3")
    engine = WingDingynouse(
        policy=bundle, trusted_keys=keys, genesis_key_ids={genesis_key_id},
        trusted_approver_key_ids={genesis_key_id}, runtime_signer=runtime, store=store,
    )
    fs = FilesystemAdapter(root / "workspace")
    adapters = AdapterRegistry()
    adapters.register("fs.read", fs.read)
    adapters.register("fs.write", fs.write)
    gate = FDTGate(engine, adapters, AuditLedger(root / "audit.jsonl"))
    token_map = TokenPrincipalMap(json.loads((root / "tokens.json").read_text("utf-8")))
    return gate, token_map, store, genesis_key_id


def cmd_demo() -> int:
    with tempfile.TemporaryDirectory(prefix="fdt-gate-") as td:
        root = Path(td)
        init_workspace(root)
        gate, _, store, _ = load_gate(root)
        genesis = Signer.load(root / "keys/genesis.pem")
        read_action = ActionEnvelope(actor="local-agent", effect="fs.read", resource="workspace/hello.txt", method="READ")
        (root / "workspace/hello.txt").write_text("table upright\n", "utf-8")
        r1 = gate.execute(read_action)
        write_action = ActionEnvelope(actor="local-agent", effect="fs.write", resource="workspace/result.txt", method="WRITE", payload={"text": "flipped safely\n"})
        r2 = gate.execute(write_action)
        now = utc_now()
        approval = issue_approval(
            signer=genesis, action_hash=write_action.action_hash, approver="genesis",
            issued_at=fmt_time(now), expires_at=fmt_time(now + timedelta(minutes=5)), one_time=True,
        )
        store.put_approval(approval)
        r3 = gate.execute(write_action)
        r4 = gate.execute(write_action)
        ok, records, error = gate.audit.verify()
        summary = {
            "read_executed": r1["executed"],
            "write_without_approval": r2["receipt"]["decision"],
            "write_with_exact_approval": r3["executed"],
            "approval_reuse": r4["receipt"]["decision"],
            "audit_valid": ok, "audit_records": records, "audit_error": error,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if all([r1["executed"], r2["receipt"]["decision"] == "REQUIRE_APPROVAL", r3["executed"], not r4["executed"], ok]) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fdt-gate")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("root")
    sub.add_parser("demo")
    s = sub.add_parser("authorize"); s.add_argument("root"); s.add_argument("action_json")
    s = sub.add_parser("execute"); s.add_argument("root"); s.add_argument("action_json")
    s = sub.add_parser("approve"); s.add_argument("root"); s.add_argument("action_hash"); s.add_argument("--minutes", type=int, default=5)
    s = sub.add_parser("revoke"); s.add_argument("root"); s.add_argument("object_id"); s.add_argument("--kind", default="capability"); s.add_argument("--reason", default="manual revocation")
    s = sub.add_parser("audit-verify"); s.add_argument("root")
    s = sub.add_parser("serve"); s.add_argument("root"); s.add_argument("--bind", default="127.0.0.1"); s.add_argument("--port", type=int, default=8767)
    args = p.parse_args(argv)

    if args.cmd == "init":
        print(json.dumps(init_workspace(Path(args.root)), indent=2, sort_keys=True)); return 0
    if args.cmd == "demo":
        return cmd_demo()

    root = Path(args.root)
    gate, token_map, store, _ = load_gate(root)
    if args.cmd in {"authorize", "execute"}:
        action = ActionEnvelope.from_dict(json.loads(Path(args.action_json).read_text("utf-8")))
        result = gate.authorize(action).to_dict() if args.cmd == "authorize" else gate.execute(action)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)); return 0
    if args.cmd == "approve":
        genesis = Signer.load(root / "keys/genesis.pem")
        now = utc_now()
        approval = issue_approval(
            signer=genesis, action_hash=args.action_hash, approver="genesis",
            issued_at=fmt_time(now), expires_at=fmt_time(now + timedelta(minutes=args.minutes)), one_time=True,
        )
        store.put_approval(approval)
        print(json.dumps(approval.to_dict(), indent=2, sort_keys=True)); return 0
    if args.cmd == "revoke":
        store.revoke(args.object_id, args.kind, fmt_time(utc_now()), args.reason)
        print("revoked", args.object_id); return 0
    if args.cmd == "audit-verify":
        ok, count, err = gate.audit.verify()
        print(json.dumps({"ok": ok, "records": count, "error": err}, indent=2)); return 0 if ok else 2
    if args.cmd == "serve":
        serve(gate, token_map, args.bind, args.port); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
