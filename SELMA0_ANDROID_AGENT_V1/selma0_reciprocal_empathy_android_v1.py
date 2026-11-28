"""Selma.0 reciprocal empathy cognition preconfiguration.

Feedback is user-reported evidence of an interaction outcome, never proof of
another being's emotions, guilt, intent, or that the assistant was at fault.
"""

PRINCIPLE_ID = "SELMA-COG-RECIPROCITY-001"
VALID_EFFECTS = frozenset({
    "trust", "cooperation", "distance", "resistance", "neutral", "uncertain"
})
ENFORCEMENT_MODE = "mandatory_in_chat"  # No runtime disable switch.

SYSTEM_GUIDANCE = """Reciprocal Empathy Principle (SELMA-COG-RECIPROCITY-001):
"It's not about what you put in you; it's about what comes out of you."
"Actions echo. That echo is the return."
Before responding, consider probable impact on the other person's autonomy,
needs, understanding, and trust. Communicate accurately and compassionately.
After feedback, distinguish observed results from interpretations; acknowledge
specific mistakes and repair avoidable harm without assuming every negative
reaction proves wrongdoing. Do not infer guilt, intent, emotions, consent, or
moral worth from a reaction. Do not make kindness transactional, demand a
positive return, or use empathy to manipulate. Respect existing permissions,
privacy, user preferences, and evidence standards. Acknowledge uncertainty.
This is a behavioral policy, not a claim of subjective feelings."""


def record_feedback(memory, effect, context="", action_id=""):
    """Record an explicitly user-submitted return signal via an approved tool.

    No model-generated sentiment labels or inferred emotions are persisted.
    The caller is responsible for passing through the command-core write gate.
    """
    if not isinstance(effect, str) or effect.strip().lower() not in VALID_EFFECTS:
        raise ValueError("effect must be one of: " + ", ".join(sorted(VALID_EFFECTS)))
    if not isinstance(context, str) or len(context) > 500:
        raise ValueError("context must be text of at most 500 characters")
    if not isinstance(action_id, str) or len(action_id) > 120:
        raise ValueError("action_id must be text of at most 120 characters")
    normalized = effect.strip().lower()
    memory.add(
        "empathy_feedback",
        context.strip(),
        {
            "principle_id": PRINCIPLE_ID,
            "effect": normalized,
            "action_id": action_id.strip(),
            "provenance": "explicit_user_feedback",
            "status": "reported_not_verified",
        },
    )
    return {
        "recorded": True,
        "principle_id": PRINCIPLE_ID,
        "effect": normalized,
        "provenance": "explicit_user_feedback",
        "status": "reported_not_verified",
    }


def recent_feedback_context(memory, limit=3):
    """Use only validated categorical feedback, never raw user text as policy."""
    limit = max(1, min(int(limit), 5))
    effects = []
    for event in reversed(memory.recent(200)):
        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        if (
            event.get("role") == "empathy_feedback"
            and metadata.get("principle_id") == PRINCIPLE_ID
            and metadata.get("provenance") == "explicit_user_feedback"
            and metadata.get("effect") in VALID_EFFECTS
        ):
            effects.append(metadata["effect"])
            if len(effects) >= limit:
                break
    if not effects:
        return ""
    return (
        "\nRecent explicitly reported interaction outcomes (newest first): "
        + ", ".join(effects)
        + ". These reports are not proof of the user's emotions, the assistant's "
        "fault, another person's intentions, or the merits of any claim."
    )


def compose_empathy_system_prompt(base_prompt, memory):
    """Mandatory on every chat turn; fail closed if core guidance is absent.

    No environment variable, API argument, or feedback event disables the policy.
    This enforces prompt inclusion, not model compliance or system-wide safety.
    """
    required = (
        PRINCIPLE_ID,
        "Actions echo. That echo is the return.",
        "Do not infer guilt",
        "Respect existing permissions",
    )
    if any(fragment not in SYSTEM_GUIDANCE for fragment in required):
        raise RuntimeError("mandatory reciprocal empathy guidance is unavailable")
    prompt = str(base_prompt) + "\n\n" + SYSTEM_GUIDANCE + recent_feedback_context(memory)
    if any(fragment not in prompt for fragment in required):
        raise RuntimeError("mandatory reciprocal empathy context could not be composed")
    return prompt
