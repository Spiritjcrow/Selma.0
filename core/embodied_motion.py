"""Renderer-neutral embodied motion planning for Selma Adult Mode."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def _approach(current: float, target: float, dt: float, tau: float) -> float:
    if dt <= 0.0:
        return current
    alpha = 1.0 - math.exp(-dt / max(tau, 1e-6))
    return current + (target - current) * alpha


@dataclass(frozen=True, slots=True)
class EmbodiedPose:
    eye_x: float
    eye_y: float
    head_yaw_deg: float
    head_pitch_deg: float
    blink: float
    breath: float
    jaw_open: float
    torso_sway_deg: float


class EyesFirstMotionController:
    """Deterministic eyes-first gaze, breathing, blinking and speech mechanics."""

    def __init__(
        self,
        *,
        eye_tau_s: float = 0.045,
        head_tau_s: float = 0.22,
        head_follow_delay_s: float = 0.12,
        max_head_yaw_deg: float = 18.0,
        max_head_pitch_deg: float = 12.0,
        blink_period_s: float = 4.2,
        blink_duration_s: float = 0.14,
        breath_period_s: float = 4.8,
    ) -> None:
        if min(
            eye_tau_s,
            head_tau_s,
            max_head_yaw_deg,
            max_head_pitch_deg,
            blink_period_s,
            blink_duration_s,
            breath_period_s,
        ) <= 0:
            raise ValueError("motion controller dimensions must be positive")
        if head_follow_delay_s < 0:
            raise ValueError("head_follow_delay_s must be non-negative")
        if blink_duration_s >= blink_period_s:
            raise ValueError("blink duration must be shorter than blink period")
        self.eye_tau_s = eye_tau_s
        self.head_tau_s = head_tau_s
        self.head_follow_delay_s = head_follow_delay_s
        self.max_head_yaw_deg = max_head_yaw_deg
        self.max_head_pitch_deg = max_head_pitch_deg
        self.blink_period_s = blink_period_s
        self.blink_duration_s = blink_duration_s
        self.breath_period_s = breath_period_s
        self.reset()

    def reset(self) -> None:
        self._time_s = 0.0
        self._eye_x = 0.0
        self._eye_y = 0.0
        self._head_yaw = 0.0
        self._head_pitch = 0.0
        self._last_target_x = 0.0
        self._last_target_y = 0.0
        self._focus_age_s = 0.0

    def tick(
        self,
        dt_seconds: float,
        *,
        gaze_x: float = 0.0,
        gaze_y: float = 0.0,
        speaking: bool = False,
        mouth_open: float = 0.0,
    ) -> EmbodiedPose:
        dt = float(dt_seconds)
        if not math.isfinite(dt) or dt < 0.0 or dt > 1.0:
            raise ValueError("dt_seconds must be finite and in [0, 1]")
        target_x = _clamp(float(gaze_x), -1.0, 1.0)
        target_y = _clamp(float(gaze_y), -1.0, 1.0)
        jaw = _clamp(float(mouth_open), 0.0, 1.0)

        target_delta = max(
            abs(target_x - self._last_target_x),
            abs(target_y - self._last_target_y),
        )
        if target_delta > 0.08:
            self._focus_age_s = 0.0
        else:
            self._focus_age_s += dt
        self._last_target_x = target_x
        self._last_target_y = target_y

        self._eye_x = _approach(self._eye_x, target_x, dt, self.eye_tau_s)
        self._eye_y = _approach(self._eye_y, target_y, dt, self.eye_tau_s)

        if self._focus_age_s >= self.head_follow_delay_s:
            head_yaw_target = target_x * self.max_head_yaw_deg
            head_pitch_target = -target_y * self.max_head_pitch_deg
        else:
            head_yaw_target = 0.0
            head_pitch_target = 0.0
        self._head_yaw = _approach(
            self._head_yaw, head_yaw_target, dt, self.head_tau_s
        )
        self._head_pitch = _approach(
            self._head_pitch, head_pitch_target, dt, self.head_tau_s
        )

        self._time_s += dt
        blink_phase = (self._time_s + 1.3) % self.blink_period_s
        if blink_phase < self.blink_duration_s:
            blink = math.sin(math.pi * blink_phase / self.blink_duration_s)
        else:
            blink = 0.0

        breath_phase = 2.0 * math.pi * self._time_s / self.breath_period_s
        breath = 0.5 + 0.5 * math.sin(breath_phase)
        torso_sway = 0.35 * math.sin(self._time_s * 0.73)

        return EmbodiedPose(
            eye_x=_clamp(self._eye_x, -1.0, 1.0),
            eye_y=_clamp(self._eye_y, -1.0, 1.0),
            head_yaw_deg=_clamp(
                self._head_yaw, -self.max_head_yaw_deg, self.max_head_yaw_deg
            ),
            head_pitch_deg=_clamp(
                self._head_pitch, -self.max_head_pitch_deg, self.max_head_pitch_deg
            ),
            blink=_clamp(blink, 0.0, 1.0),
            breath=_clamp(breath, 0.0, 1.0),
            jaw_open=jaw if speaking else jaw * 0.2,
            torso_sway_deg=torso_sway,
        )
