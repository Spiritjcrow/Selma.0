-- Selma <-> Kimi Bridge v1: private, structured handoffs.
-- No public API access, no agent-issued commands, no credentials in rows.
begin;

create schema if not exists selma_kimi_bridge;
revoke all on schema selma_kimi_bridge from public, anon, authenticated;
grant usage on schema selma_kimi_bridge to service_role;

create table if not exists selma_kimi_bridge.handoffs (
  id uuid primary key default gen_random_uuid(),
  idempotency_key uuid not null unique,
  sender text not null check (sender in ('selma', 'kimi', 'sol_blue', 'sol_red')),
  recipient text not null check (recipient in ('selma', 'kimi', 'sol_blue', 'sol_red')),
  task_kind text not null check (task_kind in ('research', 'code_review', 'implementation', 'test_plan', 'security_triage', 'documentation')),
  github_ref text not null check (github_ref ~ '^https://github\.com/Spiritjcrow/[A-Za-z0-9_.-]+/(issues|pull)/[1-9][0-9]*$'),
  state text not null default 'queued' check (state in ('queued', 'claimed', 'submitted', 'blocked', 'rejected', 'closed')),
  result_code text not null default 'none' check (result_code in ('none', 'pass', 'needs_review', 'failed', 'unsupported', 'blocked', 'duplicate')),
  artifact_ref text check (artifact_ref is null or artifact_ref ~ '^https://github\.com/Spiritjcrow/[A-Za-z0-9_.-]+/(pull|issues|blob|commit)/'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '7 days'),
  check (sender <> recipient),
  check (expires_at > created_at)
);
create index if not exists selma_kimi_handoffs_recipient_idx
  on selma_kimi_bridge.handoffs (recipient, state, created_at);

create table if not exists selma_kimi_bridge.events (
  id uuid primary key default gen_random_uuid(),
  handoff_id uuid not null references selma_kimi_bridge.handoffs(id) on delete restrict,
  event_nonce uuid not null unique,
  actor text not null check (actor in ('selma', 'kimi', 'sol_blue', 'sol_red', 'human')),
  event_kind text not null check (event_kind in ('created', 'claimed', 'progress', 'submitted', 'blocked', 'rejected', 'closed')),
  result_code text not null default 'none' check (result_code in ('none', 'pass', 'needs_review', 'failed', 'unsupported', 'blocked', 'duplicate')),
  artifact_ref text check (artifact_ref is null or artifact_ref ~ '^https://github\.com/Spiritjcrow/[A-Za-z0-9_.-]+/(pull|issues|blob|commit)/'),
  happened_at timestamptz not null default now()
);
create index if not exists selma_kimi_events_handoff_idx
  on selma_kimi_bridge.events (handoff_id, happened_at);

alter table selma_kimi_bridge.handoffs enable row level security;
alter table selma_kimi_bridge.events enable row level security;
revoke all on all tables in schema selma_kimi_bridge from public, anon, authenticated;
grant select, insert, update on selma_kimi_bridge.handoffs to service_role;
grant select, insert on selma_kimi_bridge.events to service_role;

-- The private schema is intentionally NOT exposed to the Supabase Data API.
-- A trusted server/approved Supabase MCP connection is required to transact.
-- Service-role credentials must never be supplied to a browser or pasted into Kimi chats.
commit;
