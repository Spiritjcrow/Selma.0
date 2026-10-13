"""EmberBot Mines research engine: transparent statistics, never live wagering.

The probabilities are analytical for a uniformly random Mines grid. They DO NOT
reveal unrevealed tiles or represent any proprietary Ember game payout table.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import prod
from typing import Any

BOARD_SIZE = 25
MODEL_EDGE = 0.01  # Assumption used only for illustration; NOT Ember's actual edge.


def _int(value: Any, title: str, least: int, most: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{title} must be an integer")
    try:
        parsed = int(str(value).strip())
    except (ValueError, TypeError):
        raise ValueError(f"{title} must be an integer") from None
    if str(parsed) != str(value).strip():
        raise ValueError(f"{title} must be a whole number")
    if not least <= parsed <= most:
        raise ValueError(f"{title} must be {least} to {most}")
    return parsed


def mines_stats(mines: int, revealed_safe: int, board_size: int = BOARD_SIZE) -> dict[str, float | int]:
    """Probability for uniform placement, conditional on previously safe picks."""
    mines = _int(mines, 'Mines', 1, board_size - 1)
    revealed_safe = _int(revealed_safe, 'Revealed safe tiles', 0, board_size - mines)
    unopened = board_size - revealed_safe
    safe_left = board_size - mines - revealed_safe
    next_safe = safe_left / unopened if unopened else 0.0
    survival = prod((board_size - mines - n) / (board_size - n) for n in range(revealed_safe))
    illustrative_multiplier = (1 - MODEL_EDGE) / survival
    return {
        'board_size': board_size,
        'mines': mines,
        'revealed_safe': revealed_safe,
        'unopened': unopened,
        'safe_left': safe_left,
        'next_safe_probability': next_safe,
        'survival_probability': survival,
        'illustrative_multiplier': illustrative_multiplier,
    }


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@dataclass
class Session:
    starting_balance_sats: int = 0
    records: list[dict[str, Any]] | None = None
    active: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.starting_balance_sats = _int(self.starting_balance_sats, 'Starting sats', 0, 10**15)
        if self.records is None:
            self.records = []

    @property
    def net_sats(self) -> int:
        return sum(int(item['net_sats']) for item in self.records or [])

    @property
    def tracked_balance_sats(self) -> int:
        return self.starting_balance_sats + self.net_sats

    def begin(self, bet_sats: int, mines: int) -> None:
        if self.active is not None:
            raise ValueError('Finish or discard the current round first')
        bet = _int(bet_sats, 'Bet sats', 1, 10**12)
        count = _int(mines, 'Mines', 1, BOARD_SIZE - 1)
        self.active = {'bet_sats': bet, 'mines': count, 'safe_reveals': 0, 'started_at': timestamp()}

    def mark_safe(self) -> None:
        if self.active is None:
            raise ValueError('Start a round first')
        stats = mines_stats(self.active['mines'], self.active['safe_reveals'])
        if stats['safe_left'] == 0:
            raise ValueError('No safe tiles remaining')
        self.active['safe_reveals'] += 1

    def complete(self, outcome: str, payout_sats: int = 0) -> dict[str, Any]:
        if self.active is None:
            raise ValueError('Start a round first')
        if outcome not in ('mine', 'cashout'):
            raise ValueError('Outcome must be mine or cashout')
        amount = 0 if outcome == 'mine' else _int(payout_sats, 'Actual payout sats', 0, 10**15)
        record = dict(self.active)
        record.update({
            'outcome': outcome,
            'actual_payout_sats': amount,
            'net_sats': amount - self.active['bet_sats'],
            'finished_at': timestamp(),
        })
        self.records.append(record)
        self.active = None
        return record

    def undo_last(self) -> None:
        if self.active is not None:
            raise ValueError('Finish or discard the active round before undo')
        if not self.records:
            raise ValueError('Nothing to undo')
        self.records.pop()

    def discard_active(self) -> None:
        self.active = None

    def as_dict(self) -> dict[str, Any]:
        return {'format': 1, 'starting_balance_sats': self.starting_balance_sats,
                'records': self.records, 'active': self.active, 'exported_at': timestamp(),
                'net_sats': self.net_sats, 'tracked_balance_sats': self.tracked_balance_sats}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Session':
        if data.get('format') != 1 or not isinstance(data.get('records'), list):
            raise ValueError('Unsupported session data')
        item = cls(data['starting_balance_sats'], data['records'], data.get('active'))
        return item
