PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS wisdomux_agents (
    agent_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    capability_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(capability_json)),
    status TEXT NOT NULL DEFAULT 'OFFLINE'
        CHECK (status IN ('ONLINE', 'BUSY', 'DEGRADED', 'OFFLINE', 'REVOKED')),
    last_seen_at TEXT,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS wisdomux_tasks (
    task_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    parent_task_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'OBSERVED'
        CHECK (
            state IN (
                'OBSERVED', 'CLAIMED', 'PLANNED', 'EXECUTING', 'VERIFYING',
                'REPORTED', 'HANDED_OFF', 'BLOCKED', 'DEFERRED', 'COMPLETED',
                'CANCELLED'
            )
        ),
    truth_state TEXT NOT NULL DEFAULT 'UNVERIFIED'
        CHECK (
            truth_state IN (
                'REAL', 'PREVIEW', 'INFERRED', 'UNVERIFIED', 'BLOCKED',
                'DEGRADED'
            )
        ),
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    claimed_by_agent TEXT,
    required_capability TEXT,
    approval_state TEXT NOT NULL DEFAULT 'NOT_REQUIRED'
        CHECK (
            approval_state IN (
                'NOT_REQUIRED', 'PENDING', 'APPROVED', 'DENIED', 'EXPIRED'
            )
        ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (parent_task_id)
        REFERENCES wisdomux_tasks(task_id) ON DELETE RESTRICT,
    FOREIGN KEY (claimed_by_agent)
        REFERENCES wisdomux_agents(agent_id) ON DELETE SET NULL
) STRICT;

CREATE TABLE IF NOT EXISTS wisdomux_task_dependencies (
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on_task_id),
    CHECK (task_id <> depends_on_task_id),
    FOREIGN KEY (task_id)
        REFERENCES wisdomux_tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_task_id)
        REFERENCES wisdomux_tasks(task_id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE IF NOT EXISTS wisdomux_events (
    event_id TEXT PRIMARY KEY,
    correlation_id TEXT,
    project_id TEXT NOT NULL,
    task_id TEXT,
    sender_agent TEXT,
    event_type TEXT NOT NULL,
    truth_state TEXT NOT NULL
        CHECK (
            truth_state IN (
                'REAL', 'PREVIEW', 'INFERRED', 'UNVERIFIED', 'BLOCKED',
                'DEGRADED'
            )
        ),
    payload_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(payload_json)),
    evidence_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(evidence_json) AND json_type(evidence_json) = 'array'),
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id)
        REFERENCES wisdomux_tasks(task_id) ON DELETE RESTRICT,
    FOREIGN KEY (sender_agent)
        REFERENCES wisdomux_agents(agent_id) ON DELETE SET NULL
) STRICT;

CREATE INDEX IF NOT EXISTS wisdomux_tasks_project_state_idx
    ON wisdomux_tasks(project_id, state, priority DESC, created_at);

CREATE INDEX IF NOT EXISTS wisdomux_tasks_claimed_by_idx
    ON wisdomux_tasks(claimed_by_agent, state);

CREATE INDEX IF NOT EXISTS wisdomux_events_task_time_idx
    ON wisdomux_events(task_id, created_at);

CREATE TRIGGER IF NOT EXISTS wisdomux_events_no_update
BEFORE UPDATE ON wisdomux_events
BEGIN
    SELECT RAISE(ABORT, 'wisdomux_events is append-only');
END;

CREATE TRIGGER IF NOT EXISTS wisdomux_events_no_delete
BEFORE DELETE ON wisdomux_events
BEGIN
    SELECT RAISE(ABORT, 'wisdomux_events is append-only');
END;
