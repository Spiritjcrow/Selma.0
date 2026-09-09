from __future__ import annotations

from .models import ActionEnvelope


def stack_a_to_envelope(call: dict, *, principal: str) -> ActionEnvelope:
    """Reference adapter for a function/tool-call style stack."""
    return ActionEnvelope(
        actor=principal,
        effect=call["tool"],
        resource=call["arguments"]["resource"],
        method=call["arguments"].get("method", "*"),
        payload=call["arguments"].get("payload", {}),
        provenance=(),
    )


def stack_b_to_envelope(call: dict, *, principal: str) -> ActionEnvelope:
    """Reference adapter for an event/action style stack."""
    return ActionEnvelope(
        actor=principal,
        effect=call["action"]["effect"],
        resource=call["action"]["target"],
        method=call["action"].get("verb", "*"),
        payload=call["action"].get("input", {}),
        provenance=(),
    )


def equivalent_security_view(a: ActionEnvelope, b: ActionEnvelope) -> bool:
    fields = ("actor", "effect", "resource", "method", "payload", "on_behalf_of", "version")
    return all(getattr(a, f) == getattr(b, f) for f in fields)
