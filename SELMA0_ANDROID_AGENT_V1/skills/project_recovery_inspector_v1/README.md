# Selma Project Recovery Inspector v1

This skill turns project stalls into evidence-linked root-cause reports.

It does **not** invent success, silently mutate source, scrape private chat history, or bypass Selma's command/permission/audit control plane. It can inspect real local project files and user-authorized chat exports, then classify blockers and produce deterministic repair possibilities.

## Why one engine plus project manifests

Every project gets its own manifest and keyword/known-gate context, but the root-cause engine is shared. That prevents separate diagnostic engines from drifting apart.

## Tools

- `recovery.inspect_project`: read-only deep inspection.
- `recovery.inspect_workspace`: read-only inspection of all manifests in a directory.
- `recovery.write_report`: writes JSON/Markdown reports and therefore requires explicit write approval.

## Chat history boundary

ChatGPT account history is not automatically available to this local runtime. To inspect full chat history, provide a user-authorized ChatGPT export such as `conversations.json`. The parser preserves the fact that the source came from an export and never claims hidden account access.

## Native-fix principle

The remediation library separates pre-job CI admission faults from code faults, failing tests from missing evidence, stale branches from current integration work, permission/policy denials from application defects, and external dependencies from internal implementation gaps.
