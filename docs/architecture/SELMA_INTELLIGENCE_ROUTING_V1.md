# SELMA° intelligence routing: gated research increment V1

**State:** proposed, side-effect-free policy only. Not connected to the live Android router, the OpenAI API, or a running model. Device, network, billing, and CI validation remain outstanding.

## Research motivation

The 2012 *Artificial Intelligence Algorithms* paper surveys heuristic search, A*, AO*, genetic algorithms, graph search, and optimization. These remain useful for task dependency planning and game pathfinding but do not provide frontier-level LLM weights or learned intelligence by themselves.

Current architecture is best treated as layers:

1. **Model selection:** choose a candidate based on task complexity and explicit cost/privacy preferences; preserve Android offline-first behavior.
2. **Execution:** hand candidates to the existing router and the audited permission/registry boundary; never let model text directly grant tools, permissions, or internet access.
3. **Memory:** checkpoint tasks; index local knowledge with source, confidence, retention, and user correction. Keep cross-agent memory scoped and explicitly authorized.
4. **Planning:** structured goal/AND-OR decomposition, A* only where the state/cost/heuristic are measurable; do not confuse search graphs with LLM reasoning.
5. **Verification:** independent tests, tool-output provenance, bounded retry/replay, user approvals for sensitive actions, trace redaction and hash-chained audit.
6. **Offline support:** local llama.cpp on hardware where measured to work, plus manual cloud opt-in. Never assume an Android phone can run a 70B model or a million-token context.

## This slice

`core/intelligence_policy.py` selects a candidate among `local`, `gpt-6-luna`, `gpt-6.1-sol`, and `gpt-6-astra` with these conditions:

- Default deny: online models must be explicitly enabled, approved, and listed as available.
- Offline-first: local wins except when higher quality is explicitly preferred and cloud permissions allow it.
- Sensitive data stays local unless *both* ordinary online and separate sensitive-cloud approvals are present.
- Astra requires additional premium consent, independent of normal online consent.
- Selection has **zero side effects**. It does not test accounts, transmit data, invoke models, spend funds, or execute commands.

## Integration acceptance gates

- [x] Standard-library-only deterministic policy and unit tests in this PR.
- [ ] Benchmark task-suite quality, latency and $/task on identical real tasks; verify provider model availability before passing IDs as `available_online`.
- [ ] Provider API key/authorization provisioned via server-side secrets, not checked into source or shipped in mobile APK.
- [ ] Explicit spend ceiling, token cap, deadline, user-approved cloud route, data classification and trace redaction.
- [ ] Integrate candidate selection at existing `selma0_llm_router_android_v1.py` / audited `selma.chat` boundary without bypassing current permission gates.
- [ ] Prove Android device offline inference, controlled fallback, cancellation, reconnection and battery behavior.
- [ ] Independent GitHub CI, Android/Termux smoke tests, and real-device evidence before marking runtime implemented.

## References

- Paper: https://www.researchgate.net/publication/314564271_Artificial_Intelligence_Algorithms
- OpenAI model catalog: https://developers.openai.com/api/docs/models
- Agents SDK orchestration: https://openai.github.io/openai-agents-python/multi_agent/
- LangGraph durable execution: https://langchain-ai.github.io/langgraph/concepts/durable_execution/
- MCP security and consent: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/index.mdx

Note: ChatGPT subscriptions do not by themselves establish funded API access or installed software in SelmaOS.
