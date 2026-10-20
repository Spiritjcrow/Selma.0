# Chrome VRP collaborative research board

Status: planning and coordination; no confirmed bounty finding or payout. Only test official in-scope assets and owned isolated fixtures.

| ID | Workstream | Suggested lane | Status | Evidence needed |
|---|---|---|---|---|
| VRP-01 | Verify official program scope and eligibility | Sol Blue | QUEUED | dated official URL and exclusions |
| VRP-02 | Chromium component inventory | Selma | QUEUED | version, commit, paths |
| VRP-03 | CVE and patch-diff review | Second Selma | UNASSIGNED | advisory, patch, novelty hypothesis |
| VRP-04 | Source-to-sink review | Selma | QUEUED | source references and hypothesis |
| VRP-05 | Independent adversarial review | Gemini | UNASSIGNED | critique and falsification tests |
| VRP-06 | Isolated fuzzing and regression tests | Sol Red | QUEUED | commands, logs, outcomes |
| VRP-07 | Duplicate/prior-art research | Kimi or DeepSeek | UNASSIGNED | references and comparison |
| VRP-08 | Independent reproduction | Separate reviewer | UNASSIGNED | minimal reproduction and impact |
| VRP-09 | Private report preparation | Selma | BLOCKED | verified novel eligible finding |
| VRP-10 | Submission and award status | Owner | BLOCKED | official confirmation |

## Shared record contract
One Markdown file per hypothesis under `research/chrome-vrp/findings/VRP-XXXX.md` on an isolated research branch, with fields: ID, owner, scope URL/date, Chromium version/commit, affected paths, hypothesis, method, commands actually executed, sanitized output, expected/actual, status (QUEUED/IN_PROGRESS/TESTED/REJECTED/VALIDATED), severity evidence, prior-art check, reviewer, timestamp, next action. Never place secrets, personal data, or undisclosed exploit details in public issues or chats. Use private access only. A claim is not validated until reproduced independently.

## Collaboration rules
Claim a distinct ID before work; avoid concurrent edits to the same file. Use separate branches/PRs, commit hashes, and reviewer signoff. Exchange findings by authorized GitHub access or manually copied sanitized reports. No automatic synchronization across ChatGPT, Gemini, Kimi, or DeepSeek accounts is assumed. Do not scan third-party live infrastructure or submit speculative reports. Owner controls submissions and account access.

## Copy/paste agent handoff
You are joining an authorized Chrome VRP research collaboration. Your assigned workstream is [ID]. Read the official Chrome VRP scope before research. Work only on public code and isolated local fixtures unless separately authorized under the program. Produce a concise report with exact source references, version/commit, hypothesis, commands actually run, outputs, prior-art checks, uncertainty, and next action. Never invent testing or rewards. Do not publish undisclosed vulnerabilities. Return a sanitized handoff suitable for the shared private research board. Do not edit other agents' workstreams.
