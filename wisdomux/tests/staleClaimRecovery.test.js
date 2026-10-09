'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { TaskQueue } = require('../backend/taskQueue');
const { TaskRecovery } = require('../backend/taskRecovery');

const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);

function fixture(options = {}) {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration);
  const insertAgent = db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  );
  insertAgent.run(
    'coordinator-1',
    'Coordinator One',
    'Coordinator',
    JSON.stringify({ grants: options.grants || ['task.recover_stale'] }),
    'ONLINE',
    '2026-10-09T03:00:00.000Z',
  );
  insertAgent.run(
    'worker-1',
    'Worker One',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    'ONLINE',
    '2026-10-09T03:00:00.000Z',
  );
  insertAgent.run(
    'backup-1',
    'Backup One',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    'ONLINE',
    '2026-10-09T03:00:00.000Z',
  );
  let id = 0;
  const queue = new TaskQueue(db, {
    now: () => '2026-10-09T03:01:00.000Z',
    newId: () => `queue-${++id}`,
  });
  queue.enqueue({
    taskId: 'task-1',
    projectId: 'wisdomux',
    title: 'Recover abandoned execution',
    requiredCapability: 'task.execute',
    approvalState: options.approvalState || 'APPROVED',
  });
  queue.claimNext({ projectId: 'wisdomux', agentId: 'worker-1' });
  db.prepare(
    `UPDATE wisdomux_tasks
        SET state = ?, truth_state = 'INFERRED'
      WHERE task_id = 'task-1'`,
  ).run(options.taskState || 'EXECUTING');
  db.prepare(
    "UPDATE wisdomux_agents SET status = ? WHERE agent_id = 'worker-1'",
  ).run(options.ownerStatus || 'OFFLINE');
  const recovery = new TaskRecovery(db, {
    now: () => '2026-10-09T03:02:00.000Z',
    newId: options.newId || (() => `recovery-${++id}`),
  });
  return { db, queue, recovery };
}

function release(recovery, overrides = {}) {
  return recovery.releaseStale({
    taskId: 'task-1',
    requestedBy: 'coordinator-1',
    reason: 'owner heartbeat expired',
    evidenceRefs: ['agent://worker-1/offline'],
    ...overrides,
  });
}

test('releases stale-owned work for reassignment with evidence', () => {
  const { db, queue, recovery } = fixture();

  const released = release(recovery);

  assert.equal(released.state, 'DEFERRED');
  assert.equal(released.truth_state, 'UNVERIFIED');
  assert.equal(released.claimed_by_agent, null);
  assert.equal(released.approval_state, 'APPROVED');
  const event = db.prepare(
    "SELECT * FROM wisdomux_events WHERE event_type = 'TASK_STALE_CLAIM_RELEASED'",
  ).get();
  assert.deepEqual(JSON.parse(event.payload_json), {
    previous_owner: 'worker-1',
    owner_status: 'OFFLINE',
    previous_state: 'EXECUTING',
    previous_truth_state: 'INFERRED',
    reason: 'owner heartbeat expired',
  });
  assert.deepEqual(JSON.parse(event.evidence_json), [
    'agent://worker-1/offline',
  ]);
  assert.equal(
    queue.claimNext({ projectId: 'wisdomux', agentId: 'backup-1' }).claimed_by_agent,
    'backup-1',
  );
});

test('releases work owned by a revoked agent', () => {
  const { recovery } = fixture({ ownerStatus: 'REVOKED' });

  assert.equal(release(recovery).state, 'DEFERRED');
});

test('does not take work from an online owner', () => {
  const { db, recovery } = fixture({ ownerStatus: 'ONLINE' });

  assert.throws(() => release(recovery), /task owner is not stale/);
  assert.equal(
    db.prepare("SELECT state FROM wisdomux_tasks WHERE task_id = 'task-1'").get().state,
    'EXECUTING',
  );
});

test('does not reopen terminal work', () => {
  const { recovery } = fixture({ taskState: 'COMPLETED' });

  assert.throws(() => release(recovery), /task has no recoverable stale claim/);
});

test('requires stale-claim recovery authority', () => {
  const { recovery } = fixture({ grants: ['task.retry'] });

  assert.throws(
    () => release(recovery),
    /missing capability: task.recover_stale/,
  );
});

test('requires evidence for stale-claim recovery', () => {
  const { recovery } = fixture();

  assert.throws(
    () => release(recovery, { evidenceRefs: [] }),
    /at least one evidence reference is required/,
  );
});

test('rolls back release when recovery evidence cannot be recorded', () => {
  const { db, recovery } = fixture({ newId: () => 'collision' });
  db.prepare(
    `INSERT INTO wisdomux_events
      (event_id, project_id, event_type, truth_state, created_at)
     VALUES ('collision', 'wisdomux', 'EXISTING', 'REAL', ?)`,
  ).run('2026-10-09T03:01:30.000Z');

  assert.throws(() => release(recovery), /UNIQUE constraint failed/);
  const task = db.prepare(
    "SELECT state, truth_state, claimed_by_agent FROM wisdomux_tasks WHERE task_id = 'task-1'",
  ).get();
  assert.equal(task.state, 'EXECUTING');
  assert.equal(task.truth_state, 'INFERRED');
  assert.equal(task.claimed_by_agent, 'worker-1');
});
