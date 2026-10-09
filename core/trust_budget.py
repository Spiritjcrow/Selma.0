"""Monotonic, evidence-backed workload budgets for SelmaOS.

This module is advisory: no tool execution, authorization issuance or OS
permissions. Durable SQLite storage accumulates independently verified
successes without a trust-decrement or record-deletion API. The caller's
independent verifier must establish actual proof and collaborator identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Callable
import sqlite3

from core.protocols import RiskClass


@dataclass(frozen=True, slots=True)
class VerifiedSuccess:
    """A success claim; credit requires an independent verifier."""

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
    """Advisory throughput ceilings, never permissions or guaranteed resources."""

    trust: TrustState
    max_parallel: int
    max_retries: int
    requires_authorization: bool = True


# No recency weights and no negative point adjustments.
_THRESHOLDS = (
    (0, 0, 0),
    (3, 1, 1),
    (10, 2, 2),
    (25, 3, 5),
)
_LIMITS = ((1, 0), (2, 1), (4, 2), (8, 3))


class EvidenceTrustLedger:
    """Durable proof-gated scoring with monotonic trust under supported operations.

    Proof validation, SQLite access control, file backup and tamper resistance
    are independent responsibilities of the embedding runtime. The verifier
    MUST authenticate the proof AND the independent verifier's identity.
    No authorization decisions should be delegated to this class.
    """

    def __init__(
        self,
        verify_proof: Callable[[VerifiedSuccess], bool],
        *,
        database_path: str | Path,
        clock: Callable[[], datetime] | None = None,
        max_records: int = 8192,
    ) -> None:
        if not callable(verify_proof):
            raise TypeError("independent proof verifier required")
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("database_path required")
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self._verify = verify_proof
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_records = max_records
        self._lock = RLock()
        self._db = sqlite3.connect(str(database_path), timeout=10, check_same_thread=False)
        try:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS verified_successes_v1 (
                       proof_id TEXT PRIMARY KEY,
                       actor_id TEXT NOT NULL,
                       scope TEXT NOT NULL,
                       verifier_id TEXT NOT NULL,
                       observed_utc TEXT NOT NULL
                   )"""
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS verified_successes_scope_v1 "
                "ON verified_successes_v1(actor_id, scope)"
            )
            self._db.commit()
        except Exception:
            self._db.close()
            raise

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone-aware timestamp required")
        return value.astimezone(timezone.utc)

    def accept(self, proof: VerifiedSuccess) -> None:
        """Permanently credit independently verified successes, one per ID."""
        if not isinstance(proof, VerifiedSuccess):
            raise TypeError("VerifiedSuccess required")
        if any(not isinstance(value, str) or not value.strip() for value in (
            proof.actor_id, proof.scope, proof.proof_id, proof.verifier_id
        )):
            raise ValueError("actor, scope, proof and verifier IDs must be nonempty")
        if proof.actor_id == proof.verifier_id:
            raise ValueError("self-verification prohibited")
        observed = self._utc(proof.observed_at)
        if observed > self._utc(self._clock()) + timedelta(minutes=5):
            raise ValueError("proof timestamp too far in the future")

        with self._lock:
            if self._db.execute(
                "SELECT 1 FROM verified_successes_v1 WHERE proof_id = ?",
                (proof.proof_id,),
            ).fetchone():
                raise ValueError("replayed proof ID")
            count = self._db.execute(
                "SELECT COUNT(*) FROM verified_successes_v1"
            ).fetchone()[0]
            if count >= self._max_records:
                raise RuntimeError("proof store full: preserve earned credit and fail closed")
            # Never trust merely asserted task success, including our own output.
            if self._verify(proof) is not True:
                raise ValueError("proof not independently verified")
            try:
                self._db.execute(
                    "INSERT INTO verified_successes_v1 "
                    "(proof_id, actor_id, scope, verifier_id, observed_utc) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        proof.proof_id,
                        proof.actor_id,
                        proof.scope,
                        proof.verifier_id,
                        observed.isoformat(),
                    ),
                )
                self._db.commit()
            except sqlite3.IntegrityError as exc:
                self._db.rollback()
                raise ValueError("replayed proof ID") from exc
            except Exception:
                self._db.rollback()
                raise

    def state(self, actor_id: str, scope: str) -> TrustState:
        """All-time, nondecreasing score for a particular actor and scope."""
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("actor_id required")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope required")
        with self._lock:
            successes, collaborators, days = self._db.execute(
                """SELECT COUNT(*), COUNT(DISTINCT verifier_id),
                          COUNT(DISTINCT substr(observed_utc, 1, 10))
                   FROM verified_successes_v1
                   WHERE actor_id = ? AND scope = ?""",
                (actor_id, scope),
            ).fetchone()
        tier = max(
            index
            for index, (need_successes, need_collaborators, need_days)
            in enumerate(_THRESHOLDS)
            if successes >= need_successes
            and collaborators >= need_collaborators
            and days >= need_days
        )
        return TrustState(tier, successes, collaborators, days)

    def budget(self, actor_id: str, scope: str, risk: RiskClass) -> WorkBudget:
        """Recommend increased parallel READ work, never increased authority."""
        trust = self.state(actor_id, scope)
        parallel, retries = _LIMITS[trust.tier if risk is RiskClass.READ else 0]
        return WorkBudget(trust, parallel, retries)

    def close(self) -> None:
        with self._lock:
            self._db.close()
