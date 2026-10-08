# Sol Blue / Sol Red security slice v1 (PoeLLM)

## Scope and truth state
This module is **repository code**, not evidence that the Android device, Ollama,
LiteLLM, GitHub runners, router or any other host has been inspected. Installation
and physical-device checks are separate. There is no automatic live threat scan.

- `sol.blue.exposure_review`: immediately available, read-only, network-free
  analysis of caller-declared `bind_host`, `model_host`,
  `authentication_enabled` and up to 64 `observed_ips`. Gives risk flags,
  never asserts internet reachability. Network-agnostic, no hardcoded provider.
- `sol.red.isolated_selftest`: registered and enabled but gated by **per-call
  approval** via the existing `sensitive_read` policy. Runs in-memory
  adversarial boundary assertions; it cannot attack a host, log in, scan ports,
  brute-force credentials, or execute external commands.

## How to run
With the existing command core running on its authorized local endpoint, use
`POST /api/selma0/tools/execute/v1` with a JSON object:

```json
{"tool":"sol.blue.exposure_review","arguments":{"bind_host":"127.0.0.1","model_host":"localhost","authentication_enabled":false}}
```

```json
{"tool":"sol.red.isolated_selftest","arguments":{},"approved":true}
```

The second request must be an actual user-approved invocation. UI approval
and local binding controls must not be bypassed. Requests and results are
persisted in the existing audit log. Do not submit secrets or sensitive logs.

Tests: `python3 -m unittest discover -s SELMA0_ANDROID_AGENT_V1/tests -p 'test_*.py' -v`

## Defensive response guidance
Keep inference endpoints on loopback unless authenticated and protected with
firewall/TLS or a trusted tunnel; update vulnerable packages and monitor host
processes, CPU use and outbound connections using owner-authorized tools. A
historical IOC match is a triage lead, **not proof of compromise**. Investigate
time-stamped firewall/process logs before attributing activity.

PoeLLM indicator source: Lumen Black Lotus Labs,
https://www.lumen.com/blog/en-us/canto-incognito-tracking-the-poellm-malware
(October 2026). These IP indicators are historical and may change.

## Deferred (not implemented)
Consent-based live local-process inventory, listen-socket enumeration,
authenticated endpoint health checks, SIEM correlation, opt-in lab pen testing,
emergency containment, and device-specific integration are later iterations,
requiring a concrete owned target, capability verification and separate policy.
