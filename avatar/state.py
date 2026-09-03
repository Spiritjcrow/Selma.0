"""Deterministic, side-effect-free avatar event controller.

The controller emits required effects; it never performs device, audio,
capture, presentation, or permission operations itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from core.protocols import AvatarState


class EventSource(StrEnum):
    USER = "user"
    SYSTEM = "system"
    MODEL = "model"
    AUTONOMOUS = "autonomous"


class TransitionStatus(StrEnum):
    APPLIED = "applied"
    STALE_SEQUENCE = "stale_sequence"
    STALE_GENERATION = "stale_generation"
    DISABLED = "disabled"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class AvatarEvent:
    sequence: int
    target: AvatarState
    source: EventSource
    generation_id: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if not isinstance(self.target, AvatarState):
            raise TypeError("target must be an AvatarState")
        if not isinstance(self.source, EventSource):
            raise TypeError("source must be an EventSource")
        if self.generation_id is not None and (
            not isinstance(self.generation_id, str) or not self.generation_id.strip()
        ):
            raise ValueError("generation_id must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class TransitionResult:
    status: TransitionStatus
    state: AvatarState
    sequence: int
    effects: tuple[str, ...] = ()
    message: str = ""

    @property
    def applied(self) -> bool:
        return self.status is TransitionStatus.APPLIED


_ALLOWED: dict[AvatarState, frozenset[AvatarState]] = {
    AvatarState.IDLE: frozenset({AvatarState.LISTENING, AvatarState.THINKING, AvatarState.SLEEPING, AvatarState.ERROR}),
    AvatarState.LISTENING: frozenset({AvatarState.IDLE, AvatarState.THINKING, AvatarState.SLEEPING, AvatarState.ERROR}),
    AvatarState.THINKING: frozenset({AvatarState.IDLE, AvatarState.SPEAKING, AvatarState.INTERRUPTED, AvatarState.ERROR}),
    AvatarState.SPEAKING: frozenset({AvatarState.IDLE, AvatarState.LISTENING, AvatarState.INTERRUPTED, AvatarState.ERROR}),
    AvatarState.INTERRUPTED: frozenset({AvatarState.IDLE, AvatarState.LISTENING, AvatarState.ERROR}),
    AvatarState.SLEEPING: frozenset({AvatarState.IDLE, AvatarState.LISTENING, AvatarState.ERROR}),
    AvatarState.ERROR: frozenset({AvatarState.IDLE, AvatarState.SLEEPING}),
}


class AvatarStateController:
    """Ordered FSM with user-priority interruption and a fail-closed kill switch."""

    def __init__(self, *, listening_after_interrupt: bool = True) -> None:
        self._state = AvatarState.IDLE
        self._last_sequence = -1
        self._active_generation: str | None = None
        self._enabled = True
        self._listening_after_interrupt = listening_after_interrupt
        self._dropped_stale = 0

    @property
    def state(self) -> AvatarState:
        return self._state

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def last_sequence(self) -> int:
        return self._last_sequence

    @property
    def active_generation(self) -> str | None:
        return self._active_generation

    @property
    def dropped_stale(self) -> int:
        return self._dropped_stale

    def apply(self, event: AvatarEvent) -> TransitionResult:
        if event.sequence <= self._last_sequence:
            self._dropped_stale += 1
            return TransitionResult(TransitionStatus.STALE_SEQUENCE, self._state, event.sequence, message="sequence was already applied")
        if not self._enabled:
            return TransitionResult(TransitionStatus.DISABLED, self._state, event.sequence, message="avatar kill switch is active")
        if (
            event.source is EventSource.USER
            and event.target is AvatarState.INTERRUPTED
            and self._state in {AvatarState.THINKING, AvatarState.SPEAKING}
        ):
            return self._barge_in_unchecked(event.sequence)
        if event.source in {EventSource.MODEL, EventSource.AUTONOMOUS}:
            if self._active_generation is None or event.generation_id != self._active_generation:
                self._dropped_stale += 1
                return TransitionResult(TransitionStatus.STALE_GENERATION, self._state, event.sequence, message="generation is no longer active")
        if event.target == self._state:
            self._last_sequence = event.sequence
            return TransitionResult(TransitionStatus.APPLIED, self._state, event.sequence, message="idempotent transition")
        if event.target not in _ALLOWED[self._state]:
            return TransitionResult(TransitionStatus.INVALID, self._state, event.sequence, message=f"invalid transition {self._state.value}->{event.target.value}")
        self._state = event.target
        self._last_sequence = event.sequence
        if event.source is EventSource.MODEL and event.target in {
            AvatarState.IDLE,
            AvatarState.LISTENING,
            AvatarState.ERROR,
        }:
            self._active_generation = None
        return TransitionResult(TransitionStatus.APPLIED, self._state, event.sequence)

    def begin_generation(self, generation_id: str, sequence: int) -> TransitionResult:
        if not isinstance(generation_id, str) or not generation_id.strip():
            raise ValueError("generation_id must not be empty")
        event = AvatarEvent(sequence, AvatarState.THINKING, EventSource.SYSTEM)
        result = self.apply(event)
        if result.applied:
            self._active_generation = generation_id
        return result

    def barge_in(self, sequence: int) -> TransitionResult:
        if sequence <= self._last_sequence:
            self._dropped_stale += 1
            return TransitionResult(TransitionStatus.STALE_SEQUENCE, self._state, sequence, message="sequence was already applied")
        if not self._enabled:
            return TransitionResult(TransitionStatus.DISABLED, self._state, sequence, message="avatar kill switch is active")
        return self._barge_in_unchecked(sequence)

    def _barge_in_unchecked(self, sequence: int) -> TransitionResult:
        effects = ("cancel_generation", "drain_audio")
        self._active_generation = None
        self._state = AvatarState.LISTENING if self._listening_after_interrupt else AvatarState.IDLE
        self._last_sequence = sequence
        return TransitionResult(TransitionStatus.APPLIED, self._state, sequence, effects, "user interruption applied")

    def kill(self, sequence: int) -> TransitionResult:
        if sequence <= self._last_sequence:
            self._dropped_stale += 1
            return TransitionResult(TransitionStatus.STALE_SEQUENCE, self._state, sequence, message="sequence was already applied")
        self._active_generation = None
        self._enabled = False
        self._state = AvatarState.IDLE
        self._last_sequence = sequence
        return TransitionResult(
            TransitionStatus.APPLIED,
            self._state,
            sequence,
            ("cancel_generation", "drain_audio", "stop_animation", "stop_capture", "disable_autonomy"),
            "kill switch applied",
        )

    def restart(self, sequence: int) -> TransitionResult:
        if sequence <= self._last_sequence:
            self._dropped_stale += 1
            return TransitionResult(TransitionStatus.STALE_SEQUENCE, self._state, sequence, message="sequence was already applied")
        if self._enabled:
            return TransitionResult(TransitionStatus.INVALID, self._state, sequence, message="avatar is already enabled")
        self._enabled = True
        self._state = AvatarState.IDLE
        self._last_sequence = sequence
        return TransitionResult(TransitionStatus.APPLIED, self._state, sequence, ("remain_quiet",), "explicit restart applied")

    def apply_batch(self, events: Iterable[AvatarEvent]) -> tuple[TransitionResult, ...]:
        """Apply by sequence; user events win ties and cancel later model output."""
        priority = {EventSource.USER: 0, EventSource.SYSTEM: 1, EventSource.MODEL: 2, EventSource.AUTONOMOUS: 3}
        ordered = sorted(events, key=lambda event: (event.sequence, priority[event.source]))
        return tuple(self.apply(event) for event in ordered)
