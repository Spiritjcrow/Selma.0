"""Platform-neutral SelmaOS Gate 1 capability contracts.

This package is intentionally side-effect free. External effects continue to
flow through the existing audited Android/Termux command control plane.
"""

from .protocols import (
    ALL_CAPABILITIES,
    CAPABILITY_RISK_FLOORS,
    AdapterDescriptor,
    AdapterResult,
    AvatarState,
    CancellationToken,
    Capability,
    InvocationContext,
    ResultStatus,
    RiskClass,
    SupportState,
)

__all__ = [
    "ALL_CAPABILITIES",
    "CAPABILITY_RISK_FLOORS",
    "AdapterDescriptor",
    "AdapterResult",
    "AvatarState",
    "CancellationToken",
    "Capability",
    "InvocationContext",
    "ResultStatus",
    "RiskClass",
    "SupportState",
]
