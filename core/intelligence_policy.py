"""Side-effect-free SelmaOS intelligence selection policy (proposal v1).

This module chooses a *candidate* model only. Network, model invocation,
permissions, budgets, and auditing remain with Selma's existing control plane.
The policy cannot grant access to an online service.
"""

from dataclasses import dataclass
from enum import Enum


class Workload(str, Enum):
    ROUTINE = "routine"
    CODING = "coding"
    DEEP = "deep"


LOCAL = "local"
LUNA = "gpt-6-luna"
SOL = "gpt-6.1-sol"
ASTRA = "gpt-6-astra"


@dataclass(frozen=True)
class RouteRequest:
    workload: Workload
    local_ready: bool = False
    online_enabled: bool = False
    online_approved: bool = False
    prefer_high_quality: bool = False
    sensitive: bool = False
    sensitive_cloud_approved: bool = False
    premium_approved: bool = False
    available_online: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.workload, Workload):
            raise TypeError("workload must be a Workload")
        for field_name in (
            "local_ready", "online_enabled", "online_approved",
            "prefer_high_quality", "sensitive", "sensitive_cloud_approved",
            "premium_approved",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if not isinstance(self.available_online, tuple) or any(
            not isinstance(item, str) for item in self.available_online
        ):
            raise TypeError("available_online must be a tuple of model IDs")


@dataclass(frozen=True)
class RouteDecision:
    model: str | None
    channel: str
    reason: str


def select_model(request: RouteRequest) -> RouteDecision:
    """Return a proposal. This never executes a model or approves network use."""
    if not isinstance(request, RouteRequest):
        raise TypeError("request must be a RouteRequest")

    can_cloud = request.online_enabled and request.online_approved
    if request.sensitive and not request.sensitive_cloud_approved:
        can_cloud = False

    if request.local_ready and (not request.prefer_high_quality or not can_cloud):
        return RouteDecision(LOCAL, "local", "offline-first local inference")

    if can_cloud:
        if request.workload == Workload.ROUTINE:
            candidates = (LUNA, SOL)
        elif request.workload == Workload.CODING:
            candidates = (SOL, LUNA)
        else:
            candidates = (ASTRA, SOL) if request.premium_approved else (SOL,)
        for model in candidates:
            if model in request.available_online:
                return RouteDecision(model, "online-candidate", "requires existing control-plane approval")

    if request.local_ready:
        return RouteDecision(LOCAL, "local", "online unavailable; local fallback")
    return RouteDecision(None, "unavailable", "no authorized, available model")
