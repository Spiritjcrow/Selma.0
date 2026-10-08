PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS wisdomux_proof_ledger (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    task_id TEXT,
    actor_agent TEXT NOT NULL,
    claim TEXT NOT NULL,
    truth_state TEXT NOT NULL
        CHECK (
            truth_state IN (
                'REAL', 'PREVIEW', 'INFERRED', 'UNVERIFIED', 'BLOCKED',
                'DEGRADED'
            )
        ),
    evidence_json TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(evidence_json) AND json_type(evidence_json) = 'array'),
    previous_hash TEXT
        CHECK (previous_hash IS NULL OR length(previous_hash) = 64),
    entry_hash TEXT NOT NULL UNIQUE CHECK (length(entry_hash) = 64),
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id)
        REFERENCES wisdomux_tasks(task_id) ON DELETE RESTRICT,
    FOREIGN KEY (actor_agent)
        REFERENCES wisdomux_agents(agent_id) ON DELETE RESTRICT
) STRICT;

CREATE INDEX IF NOT EXISTS wisdomux_proof_project_sequence_idx
    ON wisdomux_proof_ledger(project_id, sequence);

CREATE INDEX IF NOT EXISTS wisdomux_proof_task_sequence_idx
    ON wisdomux_proof_ledger(task_id, sequence);

CREATE TRIGGER IF NOT EXISTS wisdomux_proof_ledger_no_update
BEFORE UPDATE ON wisdomux_proof_ledger
BEGIN
    SELECT RAISE(ABORT, 'wisdomux_proof_ledger is append-only');
END;

CREATE TRIGGER IF NOT EXISTS wisdomux_proof_ledger_no_delete
BEFORE DELETE ON wisdomux_proof_ledger
BEGIN
    SELECT RAISE(ABORT, 'wisdomux_proof_ledger is append-only');
END;
