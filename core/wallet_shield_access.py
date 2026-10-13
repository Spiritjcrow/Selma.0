"""WalletShield v0.2 passive protection governance (policy preflight only).

This module decides whether a *case-specific access request may proceed to a
separate, audited authorization handler*. It never fetches, scans, sends,
reveals or unlocks member data. All credentials are references to externally
verified scoped attestations, not owner-supplied booleans. Production access
MUST use independently implemented identity/consent/warrant verification,
replay protection, expiry and revocation checks and the Selma control plane.
Without a verifier, every request is denied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
import time
from typing import Mapping, Protocol, runtime_checkable


CASE_ID = re.compile(r"[a-zA-Z0-9_-]{6,48}\Z")
TOKEN_REF = re.compile(r"[a-zA-Z0-9_-]{16,128}\Z")


class Action(StrEnum):
    COMMUNITY_PUBLIC_ADVISORY = "community_public_advisory"
    SPECIALIST_REVIEW = "specialist_review"
    SPECIALIST_RECOVERY_GUIDANCE = "specialist_recovery_guidance"
    AUTHORITY_EVIDENCE_DISCLOSURE = "authority_evidence_disclosure"


class Principal(StrEnum):
    COMMUNITY_PUBLISHER = "community_publisher"
    SPECIALIST = "specialist"
    LEGAL_AUTHORITY = "legal_authority"


# Each credential MUST be checked upstream against a cryptographic identity,
# case, operation, expiration, revocation, and replay registry.
REQUIREMENTS: dict[Action, tuple[Principal, tuple[str, ...]]] = {
    Action.COMMUNITY_PUBLIC_ADVISORY: (
        Principal.COMMUNITY_PUBLISHER,
        ("publisher_role", "editorial_review", "public_only_attestation"),
    ),
    Action.SPECIALIST_REVIEW: (
        Principal.SPECIALIST,
        ("specialist_role", "case_assignment", "victim_consent"),
    ),
    Action.SPECIALIST_RECOVERY_GUIDANCE: (
        Principal.SPECIALIST,
        ("specialist_role", "case_assignment", "victim_consent"),
    ),
    Action.AUTHORITY_EVIDENCE_DISCLOSURE: (
        Principal.LEGAL_AUTHORITY,
        ("authority_role", "court_order", "judge_authorization",
         "victim_consent", "case_scope", "independent_reviewer"),
    ),
}
ALLOWED_ATTESTATIONS = frozenset(
    requirement
    for _, requirements in REQUIREMENTS.values()
    for requirement in requirements
)


@dataclass(frozen=True, slots=True)
class AccessRequest:
    action: Action
    principal: Principal
    case_id: str | None = None
    attestations: Mapping[str, str] = field(default_factory=dict)
    # Bind every credential to ONE narrowly scoped action, and expire the
    # authorization session (not the court document).
    session_expires_at: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.action, Action) or not isinstance(self.principal, Principal):
            raise TypeError("action and principal must be enum values")
        if self.action is Action.COMMUNITY_PUBLIC_ADVISORY:
            if self.case_id is not None:
                raise ValueError("public community notices must not identify cases")
        elif type(self.case_id) is not str or not CASE_ID.fullmatch(self.case_id):
            raise ValueError("case-specific operations require a pseudonymous case_id")
        if type(self.session_expires_at) is not int:
            raise TypeError("expiry must be a UTC integer timestamp")
        if not isinstance(self.attestations, Mapping):
            raise TypeError("attestations must be a mapping")
        if any(
            type(k) is not str or k not in ALLOWED_ATTESTATIONS
            or type(v) is not str or not TOKEN_REF.fullmatch(v)
            for k, v in self.attestations.items()
        ):
            raise ValueError("attestation names or references invalid")
        if len(self.attestations) > len(ALLOWED_ATTESTATIONS):
            raise ValueError("too many attestations")


@runtime_checkable
class TrustedAttestationVerifier(Protocol):
    """An external production identity, consent and warrant verification service.

    An attestation must be signed by its *proper issuing authority*, bound to
    principal, case and requested action, unexpired, not revoked, and unused.
    A string reference, a self-declared role, a photo of an order, or a JSON
    Boolean alone must NEVER cause this method to return True.
    """
    def verify(
        self,
        *,
        attestation_type: str,
        attestation_ref: str,
        principal: Principal,
        action: Action,
        case_id: str | None,
        at_utc: int,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class GateDecision:
    eligible_for_separate_authorization: bool
    code: str
    missing_requirements: tuple[str, ...] = ()
    # This preflight module is never itself a data access or transmission grant.
    data_retrieved: bool = False
    outbound_sent: bool = False


def check_access(
    request: AccessRequest,
    verifier: TrustedAttestationVerifier | None = None,
    *,
    at_utc: int | None = None,
) -> GateDecision:
    """Fail closed and require ALL verified case-specific authorizations.

    at_utc is injectable for unit testing only: the production handler MUST
    use a trusted clock and separately repeat these checks at execution time.
    """
    if not isinstance(request, AccessRequest):
        raise TypeError("request must be AccessRequest")
    now = int(time.time()) if at_utc is None else at_utc
    if type(now) is not int or now < 0:
        raise ValueError("invalid UTC timestamp")
    if request.session_expires_at <= now or request.session_expires_at > now + 3600:
        return GateDecision(False, "session_expired_or_too_long")
    required_principal, required = REQUIREMENTS[request.action]
    if request.principal is not required_principal:
        return GateDecision(False, "role_mismatch")
    if verifier is None:
        return GateDecision(False, "trusted_verifier_unavailable")
    missing = []
    for name in required:
        ref = request.attestations.get(name)
        if ref is None:
            missing.append(name)
            continue
        try:
            valid = verifier.verify(
                attestation_type=name,
                attestation_ref=ref,
                principal=request.principal,
                action=request.action,
                case_id=request.case_id,
                at_utc=now,
            )
        except Exception:
            valid = False
        if valid is not True:
            missing.append(name)
    if missing:
        return GateDecision(False, "authorization_incomplete", tuple(missing))
    return GateDecision(True, "eligible_for_independent_case_authorization")


def passive_community_settings() -> dict[str, object]:
    """Explicit non-surveillance defaults; advisory rules can run locally.

    This is a metadata snapshot, not a running monitoring service.
    """
    return {
        "local_on_device_advisories": True,
        "individual_device_telemetry_collection": False,
        "member_tracking": False,
        "message_interception": False,
        "wallet_secrets_collection": False,
        "community_telemetry_opt_in": False,
        "remote_specialist_access": False,
        "remote_authority_access": False,
        "automatic_authority_reporting": False,
    }
