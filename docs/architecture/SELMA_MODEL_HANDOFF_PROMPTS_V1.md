# Selma multi-model handoff prompts v0.1

Use these prompts only in independently authorized chat sessions. They do not establish automatic communication or permissions. Share public or specifically approved redacted summaries, never private repository source or keys without authorization.

## DeepSeek: ideas and tradeoffs

Given a public description of Selma: an offline-first Android/Termux assistant, with five optional API adapters and a fail-closed network default, propose at most three focused improvements. For each provide expected value, possible failure, a reproducible offline test and how it avoids paid API dependence. Do not imply that you ran code or had access to the user's private GitHub repository.

## Gemini: next review after DeepSeek

Review the supplied redacted DeepSeek proposals. Classify each ACCEPT, REVISE, REJECT or NEEDS_TEST based on evidence and the fail-closed adapter contract. Recommend one smallest testable implementation change and a rollback path. Do not invent provider access, source inspection, device execution or permissions.

## Claude Fable 5.2: API/architecture critique

Review the redacted text adapter design. Look for schema errors, API version incompatibilities, secret leakage, billing risks, provider retention constraints and paths bypassing local user approval. Return minimal reproducible tests and a bounded patch plan. Do not claim to have deployed changes.

## Grok: adversarial critique

Critique the redacted provider architecture and identify false assumptions about model names, provider capabilities, account credits, authentication, failover and evidence. Provide safe test cases and measured concerns rather than unsupported verdicts.

## Kimi: source quality feedback

Review a public, redacted Python standard-library provider adapter. Focus on portability in Termux, protocol correctness, no unexpected network calls, failure isolation and readable error responses. Suggest no more than three changes with offline regression tests.

## Black / Orange reconciliation

Keep each model's response explicitly attributed to its source and date. Black coordinates scoped revisions; Orange may run offline tests and document evidence. Independent White/Gray access is not assumed. The owner approves data sharing, provider billing and any production routing activation.
