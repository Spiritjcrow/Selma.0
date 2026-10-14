# SelmaOS Instance Roster and Handoff Protocol (proposal v0.1)

Status: **DESIGN ONLY**. No continuous runner, cross-chat messaging, voice DSP, or human identity verification is activated by this document.

## AI instance directory (fictional project identifiers, not government documents)
| Project ID | Instance | Voice persona (English regional target) | Work lane | Progress |
| --- | --- | --- | --- | --- |
| SEL-AI-001 | Coordinator | Argentine | coordination | unmeasured |
| SEL-AI-002 | Black | Northern Mexican | builder | unmeasured |
| SEL-AI-003 | White | Spain Spanish | independent QA | unmeasured |
| SEL-AI-004 | Red | Armenian | security | unmeasured |
| SEL-AI-005 | Blue | Scottish | discovery | unmeasured |
| SEL-AI-006 | UltraViolet | Brazilian | security research | planned |

These are persona designations, **not** claims of independent running processes, accents already audible, employment, citizenship, or driving privileges. No license numbers, real photographs, DOB, addresses, or signatures should be invented. A generated avatar, if later approved, must be labeled **FICTIONAL AI PROJECT BADGE**.

## Handoff envelope
- task_id, owner_instance_id, target_instance_id, repository/ref, change summary
- artifact SHA or PR URL, test command and expected outcome, evidence, blocking risks
- status: QUEUED / IN_PROGRESS / READY_FOR_QA / PASS / FAIL / BLOCKED / REVIEWED
- timestamps in UTC, revision, next action; never embed tokens, credentials or personal data
- ACK from receiving instance required before marking handoff received
- one owner for each active task; independent QA does not self-certify its own builder changes

## Progress computation
Only report **measured** completion per instance:
completed verified acceptance criteria / total assigned acceptance criteria * 100.
If no accepted criteria or runtime evidence exist, report **N/A**, not a fabricated percentage.
A role may be assigned but offline. A queue entry is not proof of execution.

## Continuity and safety
A persistent authenticated runner is needed for unattended execution; chat prompts alone do not provide it.
Queue tasks while an instance is unavailable, retry with bounded backoff, and deduplicate using task_id+revision.
Never bypass issue #43 authentication, trusted approvals, issue #44 privacy requirements, or independent QA.
Do not auto-merge, deploy, alter accounts, or grant device privileges. Milestone-only user notifications except critical verified findings.

## Human participants
Owner/architect, spouse, and Christopher Ince are named project collaborators by user description, **not** verified accounts or employees. Daughters are potential future participants only; do not provision access without explicit invitation and consent.
