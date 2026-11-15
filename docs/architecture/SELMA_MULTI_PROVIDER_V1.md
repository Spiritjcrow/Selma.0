# Selma multi-provider text adapters v0.1

Status: DRAFT, standalone Python implementation for later Selma command-core integration. Production routing is unchanged. No API keys, paid API calls, background workers or autonomous provider messages are enabled by this branch.

## Roles and handoffs

- Black: architect, scope changes and build evidence; project lead.
- Orange (formerly the Ince supporting Red phone): source review, offline QA and documentation. Orange cannot impersonate an independently authenticated White tester.
- White: independent device/session acceptance when available.
- Gray: integration reconciliation after authorized GitHub access.
- Sol Red: security owner for issue #43, separate from the Orange phone.
- Owner: grants permissions and approves production activation, billing and release.

The adapter module under SELMA0_ANDROID_AGENT_V1/selma0_provider_layers_v1.py implements explicit, one-at-a-time text requests only:

| Adapter | API endpoint | Credential environment | Model |
|---|---|---|---|
| claude | https://api.anthropic.com/v1/messages | ANTHROPIC_API_KEY | claude-fable-5-2 |
| grok | https://api.x.ai/v1/responses | XAI_API_KEY | grok-4.7 |
| gemini | https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent | GEMINI_API_KEY | SELMA_GEMINI_MODEL required |
| kimi | https://api.moonshot.ai/v1/chat/completions | KIMI_API_KEY | SELMA_KIMI_MODEL required |
| deepseek | https://api.deepseek.com/chat/completions | DEEPSEEK_API_KEY | deepseek-flash |

Other model ID overrides: SELMA_CLAUDE_MODEL, SELMA_GROK_MODEL and SELMA_DEEPSEEK_MODEL. Verify current model availability and pricing before authorizing a paid request. Access to free chat apps does not grant API credits, identity or unattended execution.

## Copy-and-paste local tests (Python 3.11+ or Termux)

Run from the checkout root:

~~~sh
python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_selma0_provider_layers_v1.py' -v
python3 -m py_compile SELMA0_ANDROID_AGENT_V1/selma0_provider_layers_v1.py
python3 SELMA0_ANDROID_AGENT_V1/selma0_provider_layers_v1.py --list
python3 SELMA0_ANDROID_AGENT_V1/selma0_provider_layers_v1.py --provider claude --message 'Test Selma provider routing'
~~~

The last command is BLOCKED with no network call because --execute is missing. Only for a deliberate, authorized, potentially billable API request, configure the correct secret from a protected credential mechanism, then use:

~~~sh
python3 SELMA0_ANDROID_AGENT_V1/selma0_provider_layers_v1.py --provider claude --execute --message 'Explain Selma provider adapters'
~~~

Never place keys or private material in GitHub issue bodies, prompts or command-line arguments. Do not use --execute unless the owner agrees to the data sharing, billing and data-retention implications.

## Limits, safeguards and follow-up

- The transport is HTTPS and endpoints are fixed to the five official provider hosts. Invalid roles/model identifiers fail closed.
- Network traffic is denied by default, no fallback from one provider to another, no task scheduling, no MCP privileges.
- Response sizes are capped; API keys and raw error payloads are not returned. Mocked tests use injected fake responses; no production mock is advertised.
- This is NOT connected to Selma's production HTTP router or trusted user approval/session verification. Issue #43 must resolve the authentication boundary before activation.
- Claude Fable 5.2 has documented 30-day data retention requirements. Avoid sensitive data unless permitted by the service terms and owner.
- The 11 offline tests check format, denial behavior and fake responses. They do not establish live API compatibility, an Android APK or independent White acceptance.
- PR #50 and issue #49 retain separate device-review gates; the source branch must not be merged or released solely on mocked API contract tests.

Evaluation rubric for future authorized comparisons: identical *public non-sensitive* prompts; actual provider/model IDs and run dates; correctness against independent evidence; instruction-following; safety/privacy limitations; latency; cost; reproducibility. Unexecuted providers remain UNTESTED, not rated. Provider-to-provider sharing requires a separate owner-authorized operation under existing issue #24 control-plane rules.

References:
- https://platform.claude.com/docs/en/models/fable-5-2/overview
- https://platform.claude.com/docs/en/api/versioning
- https://docs.x.ai/developers/rest-api-reference/inference/responses
- https://ai.google.dev/api/generate-content
- https://api-docs.deepseek.com/updates/
