from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
import os
import shutil

class ActionMode(str, Enum):
    EXECUTE = "execute"
    SIMULATE = "simulate"
    PROPOSE = "propose"
    BLOCKED = "blocked"

@dataclass(slots=True)
class CapabilityDecision:
    capability: str
    mode: ActionMode
    reason: str
    requires_elevation: bool = False
    available: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d

class CapabilityBroker:
    SAFE_LOCAL = {"scan", "index", "hash", "classify", "dedupe", "map", "report", "read", "plan", "test", "simulate", "archive", "embed-metadata"}
    PRIVILEGED = {"install-system-package", "write-system-config", "manage-service", "mount-device", "device-admin", "network-admin"}

    def __init__(self, minimal_questions: bool = True, max_questions: int = 1):
        self.minimal_questions = minimal_questions
        self.max_questions = max_questions

    @staticmethod
    def is_root() -> bool:
        return hasattr(os, "geteuid") and os.geteuid() == 0

    @staticmethod
    def has_sudo() -> bool:
        return shutil.which("sudo") is not None

    def decide(self, capability: str, *, destructive: bool = False, safety_blocked: bool = False, supported: bool = True) -> CapabilityDecision:
        if safety_blocked:
            return CapabilityDecision(capability, ActionMode.BLOCKED, "Hard safety boundary: do not execute; generate a safe alternative instead.", available=supported)
        if not supported:
            return CapabilityDecision(capability, ActionMode.PROPOSE, "Capability is not available in this runtime; produce a concrete handoff or implementation plan.", available=False)
        if destructive:
            return CapabilityDecision(capability, ActionMode.PROPOSE, "Destructive mutation requires an explicit, reviewable execution step.")
        if capability in self.PRIVILEGED and not self.is_root():
            if self.has_sudo():
                return CapabilityDecision(capability, ActionMode.PROPOSE, "Host is not currently elevated. A sudo-capable command may be prepared for legitimate user execution.", requires_elevation=True)
            return CapabilityDecision(capability, ActionMode.SIMULATE, "Host is not elevated and sudo is unavailable; validate the operation in simulation/sandbox mode.", requires_elevation=True)
        return CapabilityDecision(capability, ActionMode.EXECUTE, "Capability is locally available.")

    def policy_snapshot(self) -> dict:
        return {
            "behavior": "attempt-first",
            "minimal_questions": self.minimal_questions,
            "max_questions_before_best_effort": self.max_questions,
            "fallback_order": ["execute", "simulate", "propose-safe-alternative", "record-blocker"],
            "truthfulness": "never claim privilege, connectivity, completion, or test results that were not observed",
            "safety": "hard boundaries remain enforced",
        }
