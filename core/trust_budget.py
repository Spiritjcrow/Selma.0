"""Monotonic, evidence-backed workload budgets for SelmaOS.

This module is advisory. It never grants capabilities, credentials,
authorizations or permissions, and never dispatches external actions.
All evidence must be checked by a caller-supplied independent verifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Callable

from core.protocols import RiskClass


@dataclass(frozen=True, slots=True)
class VerifiedSuccess:
    """A claimed success that still requires independent verification."""

    actor_id: str
    scope: str
    proof_id: str
    verifier_id: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class TrustState:
    tier: int
    successes: int
    collaborators: int
    distinct_days: int


@dataclass(frozen=True, slots=True)
class WorkBudget:
    """Recommendations only; caller must separately authorize every operation."""

    trust: TrustState
    max_parallel: int
    max_retries: int
    requires_authorization: bool = True


# Tier thresholds are intentionally conservative and never time-decay.
# Independent verifiers and different observation days are necessary at
# higher tiers; accumulating raw self-reports cannot increase trust.
_THRESHOLDS = (
    (0, 0, 0),
    (3, 1, 1),
    (10, 2, 2),
    (25, 3, 5),
)
_LIMITS = ((1, 0), (2, 1), (4, 2), (8, 3))


class EvidenceTrustLedger:
    """In-memory pilot; not a production audit ledger or credential issuer.

    The verifier MUST independently establish proof authenticity, verifier
    identity, and ownership of the scoped outcome. Caller-controlled strings
    alone are not evidence. Accepted successes are never removed or discounted.
    """

    def __init__(
        self,
        verify_proof: Callable[[VerifiedSuccess], bool],
        *,
        clock: Callable[[], datetime] | None = None,
        max_records: int = 8192,
    ) -> None:
        if not callable(verify_proof):
            raise TypeError("independent proof verifier required")
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self._verify = verify_proof
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_records = max_records
        self._records: list[VerifiedSuccess] = []
        self._seen: set[str] = set()
        self._lock = RLock()

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone-aware timestamp required")
        return value.astimezone(timezone.utc)

    def accept(self, proof: VerifiedSuccess) -> None:
        """Accrue only independently verified successes, once per proof ID."""
        if not isinstance(proof, VerifiedSuccess):
            raise TypeError("VerifiedSuccess required")
        if any(not isinstance(value, str) or not value.strip() for value in (
            proof.actor_id, proof.scope, proof.proof_id, proof.verifier_id
        )):
            raise ValueError("actor, scope, proof and verifier IDs must be nonempty")
        if proof.actor_id == proof.verifier_id:
            raise ValueError("self-verification prohibited")
        if self._utc(proof.observed_at) > self._utc(self._clock()) + timedelta(minutes=5):
            raise ValueError("proof timestamp too far in the future")
        with self._lock:
            if proof.proof_id in self._seen:
                raise ValueError("replayed proof ID")
            if len(self._records) >= self._max_records:
                raise RuntimeError("proof store full; preserve earned trust and fail closed")
            # No exception or false result from the independent verifier can
            # create trust. Checking inside the lock prevents double credit.
            if self._verify(proof) is not True:
                raise ValueError("proof not independently verified")
            self._records.append(proof)
            self._seen.add(proof.proof_id)

    def state(self, actor_id: str, scope: str) -> TrustState:
        """All-time, nondecreasing score for one actor and operation scope."""
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("actor_id required")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope required")
        with self._lock:
            items = [p for p in self._records if p.actor_id == actor_id and p.scope == scope]
        successes = len(items)
        collaborators = len({p.verifier_id for p in items})
        days = len({self._utc(p.observed_at).date() for p in items})
        tier = max(
            i for i, (need_successes, need_collaborators, need_days)
            in enumerate(_THRESHOLDS)
            if successes >= need_successes
            and collaborators >= need_collaborators
            and days >= need_days
        )
        return TrustState(
            tier=tier,
            successes=successes,
            collaborators=collaborators,
            distinct_days=days,
        )

    def budget(self, actor_id: str, scope: str, risk: RiskClass) -> WorkBudget:
        """Earned recommendations do NOT override mandatory permission gates.

        Even a high-trust actor receives only baseline work budgets for
        sensitive reads, writes, and external effects.
        """
        trust = self.state(actor_id, scope)
        index = trust.tier if risk is RiskClass.READ else 0
        parallel, retries = _LIMITS[index]
        return WorkBudget(trust, parallel, retries)
