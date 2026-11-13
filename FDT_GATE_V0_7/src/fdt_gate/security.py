from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .canonical import canonical_json, fmt_time, parse_time, sha256_hex, stable_id, utc_now
from .crypto import Keyring, Signer
from .models import ActionEnvelope, Approval, CapabilityGrant, Decision, DecisionReceipt, PolicyBundle
from .policy import match_rule, verify_policy
from .store import SecurityStore


class WingDingynouse:
    """HARDSTONE deterministic authorization kernel.

    Model intent is data. Authority must arrive through a verified policy and a
    verified capability chain; approval is exact-action bound and revocable.
    """

    def __init__(
        self,
        *,
        policy: PolicyBundle,
        trusted_keys: Keyring,
        genesis_key_ids: set[str],
        runtime_signer: Signer,
        store: SecurityStore,
        trusted_approver_key_ids: set[str] | None = None,
        clock=utc_now,
    ):
        self.policy = policy
        self.keys = trusted_keys
        self.genesis_key_ids = set(genesis_key_ids)
        self.runtime_signer = runtime_signer
        self.store = store
        self.trusted_approver_key_ids = set(trusted_approver_key_ids or genesis_key_ids)
        self.clock = clock
        if not verify_policy(policy, trusted_keys):
            raise ValueError("policy bundle signature/build identity verification failed")
        if policy.signer_key_id not in self.genesis_key_ids:
            raise ValueError("policy signer is not a trusted Genesis key")

    def _verify_grant_chain(self, grant: CapabilityGrant, now: datetime, seen: set[str] | None = None) -> bool:
        seen = set() if seen is None else set(seen)
        if grant.grant_id in seen or self.store.is_revoked(grant.grant_id):
            return False
        seen.add(grant.grant_id)
        if not self.keys.verify(grant.issuer_key_id, canonical_json(grant.unsigned_dict()), grant.signature):
            return False
        if not (parse_time(grant.not_before) <= now < parse_time(grant.expires_at)):
            return False

        if grant.parent_id is None:
            return grant.issuer_key_id in self.genesis_key_ids and grant.issuer == "genesis"

        parent = self.store.get_grant(grant.parent_id)
        if parent is None or not self._verify_grant_chain(parent, now, seen):
            return False
        if grant.issuer != parent.subject:
            return False
        if grant.capability != parent.capability:
            return False
        if not grant.resource_prefix.startswith(parent.resource_prefix):
            return False
        if not set(grant.effects).issubset(parent.effects):
            return False
        if not set(grant.methods).issubset(parent.methods):
            return False
        if parse_time(grant.expires_at) > parse_time(parent.expires_at):
            return False
        if parse_time(grant.not_before) < parse_time(parent.not_before):
            return False
        return True

    def _grant_authorizes(self, grant: CapabilityGrant, action: ActionEnvelope, capability: str, now: datetime) -> bool:
        if grant.subject != action.actor or grant.capability != capability:
            return False
        if not action.resource.startswith(grant.resource_prefix):
            return False
        if action.effect not in grant.effects:
            return False
        if "*" not in grant.methods and action.method not in grant.methods:
            return False
        return self._verify_grant_chain(grant, now)

    def _find_approval(self, action_hash: str, now: datetime) -> Approval | None:
        for approval, consumed in self.store.approvals_for_action(action_hash):
            if consumed and approval.one_time:
                continue
            if self.store.is_revoked(approval.approval_id):
                continue
            if approval.action_hash != action_hash:
                continue
            if approval.signer_key_id not in self.trusted_approver_key_ids:
                continue
            if now >= parse_time(approval.expires_at):
                continue
            if not self.keys.verify(
                approval.signer_key_id, canonical_json(approval.unsigned_dict()), approval.signature
            ):
                continue
            return approval
        return None

    def _receipt(self, *, decision: Decision, reason: str, action: ActionEnvelope,
                 now: datetime, rule_id: str | None = None, grant_id: str | None = None,
                 approval_id: str | None = None) -> DecisionReceipt:
        state_hash = "sha256:" + sha256_hex(canonical_json({
            "policy": self.policy.build_id,
            "revocations": self.store.revocation_fingerprint(),
        }))
        unsigned = DecisionReceipt(
            decision=decision, reason_code=reason, action_hash=action.action_hash,
            policy_build_id=self.policy.build_id, evaluated_at=fmt_time(now),
            runtime_key_id=self.runtime_signer.key_id, rule_id=rule_id,
            grant_id=grant_id, approval_id=approval_id, state_hash=state_hash,
        )
        return replace(unsigned, signature=self.runtime_signer.sign(canonical_json(unsigned.unsigned_dict())))

    def authorize(self, action: ActionEnvelope, *, consume_approval: bool = False,
                  record_budget: bool = True) -> DecisionReceipt:
        now = self.clock()
        rule = match_rule(self.policy, action.effect, action.resource, action.method)
        if rule is None:
            return self._receipt(
                decision=self.policy.default_decision, reason="NO_MATCHING_RULE",
                action=action, now=now,
            )
        if len(canonical_json(action.payload)) > rule.max_payload_bytes:
            return self._receipt(
                decision=Decision.DENY, reason="PAYLOAD_BUDGET_EXCEEDED",
                action=action, now=now, rule_id=rule.rule_id,
            )
        if rule.decision == Decision.DENY:
            return self._receipt(
                decision=Decision.DENY, reason="POLICY_DENY", action=action, now=now, rule_id=rule.rule_id
            )
        if rule.decision == Decision.ESCALATE:
            return self._receipt(
                decision=Decision.ESCALATE, reason="POLICY_ESCALATE", action=action, now=now, rule_id=rule.rule_id
            )

        grant = next((g for g in self.store.grants_for_subject(action.actor)
                      if self._grant_authorizes(g, action, rule.capability, now)), None)
        if grant is None:
            return self._receipt(
                decision=Decision.DENY, reason="NO_VALID_CAPABILITY",
                action=action, now=now, rule_id=rule.rule_id,
            )

        if not self.store.check_rate(
            action.actor, rule.rule_id, now.timestamp(), rule.max_calls_per_minute, record_budget
        ):
            return self._receipt(
                decision=Decision.DENY, reason="RATE_BUDGET_EXCEEDED",
                action=action, now=now, rule_id=rule.rule_id, grant_id=grant.grant_id,
            )

        if rule.decision == Decision.REQUIRE_APPROVAL:
            approval = self._find_approval(action.action_hash, now)
            if approval is None:
                return self._receipt(
                    decision=Decision.REQUIRE_APPROVAL, reason="EXACT_ACTION_APPROVAL_REQUIRED",
                    action=action, now=now, rule_id=rule.rule_id, grant_id=grant.grant_id,
                )
            if consume_approval and approval.one_time:
                if not self.store.consume_approval(approval.approval_id, action.action_hash, fmt_time(now)):
                    return self._receipt(
                        decision=Decision.REQUIRE_APPROVAL, reason="APPROVAL_ALREADY_CONSUMED",
                        action=action, now=now, rule_id=rule.rule_id, grant_id=grant.grant_id,
                    )
            return self._receipt(
                decision=Decision.ALLOW, reason="APPROVED_EXACT_ACTION",
                action=action, now=now, rule_id=rule.rule_id,
                grant_id=grant.grant_id, approval_id=approval.approval_id,
            )

        return self._receipt(
            decision=Decision.ALLOW, reason="CAPABILITY_AND_POLICY_ALLOW",
            action=action, now=now, rule_id=rule.rule_id, grant_id=grant.grant_id,
        )


def issue_grant(
    *, signer: Signer, issuer: str, subject: str, capability: str, resource_prefix: str,
    effects: tuple[str, ...], methods: tuple[str, ...], not_before: str, expires_at: str,
    issued_at: str, parent_id: str | None = None,
) -> CapabilityGrant:
    base = CapabilityGrant(
        grant_id=stable_id("grant", {
            "issuer": issuer, "subject": subject, "capability": capability,
            "resource_prefix": resource_prefix, "effects": effects, "methods": methods,
            "not_before": not_before, "expires_at": expires_at, "parent_id": parent_id,
        }),
        issuer=issuer, issuer_key_id=signer.key_id, subject=subject, capability=capability,
        resource_prefix=resource_prefix, effects=effects, methods=methods,
        not_before=not_before, expires_at=expires_at, issued_at=issued_at,
        parent_id=parent_id,
    )
    return replace(base, signature=signer.sign(canonical_json(base.unsigned_dict())))


def issue_approval(*, signer: Signer, action_hash: str, approver: str,
                   issued_at: str, expires_at: str, one_time: bool = True) -> Approval:
    base = Approval(
        approval_id=stable_id("approval", {
            "action_hash": action_hash, "approver": approver,
            "issued_at": issued_at, "expires_at": expires_at,
        }),
        action_hash=action_hash, approver=approver, signer_key_id=signer.key_id,
        issued_at=issued_at, expires_at=expires_at, one_time=one_time,
    )
    return replace(base, signature=signer.sign(canonical_json(base.unsigned_dict())))


def verify_decision_receipt(receipt: DecisionReceipt, keyring: Keyring) -> bool:
    """Verify the runtime signature on a decision receipt."""
    return keyring.verify(
        receipt.runtime_key_id,
        canonical_json(receipt.unsigned_dict()),
        receipt.signature,
    )
