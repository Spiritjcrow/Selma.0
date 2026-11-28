# Selma.0 Reciprocal Empathy Drive V1

**Principle ID:** `SELMA-COG-RECIPROCITY-001`

> It's not about what you put in you; it's about what comes out of you.

> Actions echo. That echo is the return.

The Android/Termux chat runtime includes the Reciprocal Empathy
preconfiguration in every language-model chat system context. This is a
mandatory core behavioral principle, not a user-configurable feature or
optional affect filter. No runtime on/off switch exists. If the required
guidance is missing, system-context composition raises an error rather than
silently omitting it. Each reply should consider its intended impact,
preserve another being's autonomy, and distinguish observed consequences
from inferred motives or emotions.

**Coverage boundary:** This V1 enforcement covers prompt composition for
the existing chat path. It is not yet a system-wide policy kernel for
non-chat commands, independent agents, or device actions. Prompt inclusion
does not guarantee a language model's compliance, prevent all harm, or
imply Selma experiences empathy. Permission checks, safety policy, and
audits remain independent mandatory controls. A crashed or unavailable
runtime cannot be described as active. System-wide always-on compliance
requires additional integration and validation.

**Return signals:** A user may explicitly submit an outcome of `trust`,
`cooperation`, `distance`, `resistance`, `neutral`, or `uncertain`.
Signals are persisted as user-reported, unverified events in existing local
SQLite memory. Only bounded categorical outcomes enter subsequent system
context. Free-text context is stored for traceability but not injected into
system instructions. No automatic emotion, guilt, or wrongdoing detection runs.

**Authorized submission:** The existing
`POST /api/selma0/tools/execute/v1` endpoint, using:
```json
{
  "tool": "selma.empathy.feedback",
  "arguments": {
    "effect": "cooperation",
    "context": "The previous explanation enabled a shared decision",
    "action_id": "optional-local-reference"
  },
  "approved": true
}
```
The `write` classification requires explicit approval through the existing
command router and audit; a user report never overrides that policy.

**Side effects and limitations:** Adds a bounded system instruction and may
slightly increase tokens/latency. Feedback and optional context are saved in
the existing unencrypted on-device SQLite store. This V1 does not expose a
dedicated per-feedback deletion endpoint; clearing the existing conversation
memory also clears feedback, but removes other stored conversation events. Behavior can drift toward over-accommodation, so
the policy prohibits transactional kindness, manipulation, automatic blame,
and treating reports as facts. The module does not perform autonomous actions,
does not change any Android permissions, and is not evidence of AI emotion.

**Verification:** Run
`python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v`.
Portable tests cover valid/invalid outcomes, provenance, feedback limits,
and prompt-injection isolation. This feature still requires Android smoke
and physical-device verification before production claims.
