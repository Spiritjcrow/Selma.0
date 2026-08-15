from dataclasses import dataclass


@dataclass(frozen=True)
class Selma0PermissionDecisionAndroidV1:
    allowed: bool
    requires_approval: bool
    reason: str
    risk: str


class Selma0PermissionEngineAndroidV1:
    """Fail-closed permission policy for registered Selma tools."""

    READ = "read"
    SENSITIVE_READ = "sensitive_read"
    WRITE = "write"
    EXTERNAL_EFFECT = "external_effect"

    VALID_RISKS = {READ, SENSITIVE_READ, WRITE, EXTERNAL_EFFECT}

    def evaluate(self, tool_descriptor, approved=False):
        if not isinstance(tool_descriptor, dict):
            return Selma0PermissionDecisionAndroidV1(
                False, False, "tool descriptor missing", "unknown"
            )

        risk = str(tool_descriptor.get("risk", "")).strip()
        enabled = tool_descriptor.get("enabled") is not False
        if not enabled:
            return Selma0PermissionDecisionAndroidV1(
                False, False, "tool is disabled", risk or "unknown"
            )
        if risk not in self.VALID_RISKS:
            return Selma0PermissionDecisionAndroidV1(
                False, False, "tool has an invalid or missing risk class", risk or "unknown"
            )

        if risk == self.READ:
            return Selma0PermissionDecisionAndroidV1(
                True, False, "read-only capability allowed", risk
            )

        if approved is True:
            return Selma0PermissionDecisionAndroidV1(
                True, True, "explicit user approval supplied", risk
            )

        return Selma0PermissionDecisionAndroidV1(
            False,
            True,
            "explicit user approval required for this capability",
            risk,
        )

    def status(self):
        return {
            "policy": "fail_closed",
            "read_only_default": True,
            "approval_required_for": [
                self.SENSITIVE_READ,
                self.WRITE,
                self.EXTERNAL_EFFECT,
            ],
            "valid_risks": sorted(self.VALID_RISKS),
        }
