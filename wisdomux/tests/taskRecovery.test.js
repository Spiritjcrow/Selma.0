'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { TaskRecovery } = require('../backend/taskRecovery');
const { TaskQueue } = require('../backend/taskQueue');

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
     VALUES (?, ?, 'Coordinator', ?, 'ONLINE', ?)`,
  );
  insertAgent.run(
    'coordinator-1',
    'Coordinator One',
    JSON.stringify({ grants: options.grants || ['task.retry'] }),
    '2026-10-08T22:00:00.000Z',
  );
  let id = 0;
  const queue = new TaskQueue(db, {
    now: () => '2026-10-08T22:01:00.000Z',
    newId: () => `queue-${++id}`,
  });
  queue.enqueue({
    taskId: 'task-1',
    projectId: 'wisdomux',
    title: 'Recover failed work',
  });
  db.prepare(
    `UPDATE wisdomux_tasks
        SET state = ?, truth_state = 'BLOCKED', approval_state = ?,
            claimed_by_agent = NULL
      WHERE task_id = 'task-1'`,
  ).run(options.state || 'BLOCKED', options.approvalState || 'NOT_REQUIRED');
  const recovery = new TaskRecovery(db, {
    maxRetries: options.maxRetries || 3,
    now: () => '2026-10-08T22:02:00.000Z',
    newId: options.newId || (() => `retry-${++id}`),
  });
  return { db, recovery };
}

test('requeues blocked work with evidence and a numbered attempt', () => {
  const { db, recovery } = fixture();

  const task = recovery.retry({
    taskId: 'task-1',
    requestedBy: 'coordinator-1',
    reason: 'alternate adapter available',
    evidenceRefs: ['recovery://adapter/loopback'],
  });

  assert.equal(task.state, 'DEFERRED');
  assert.equal(task.truth_state, 'UNVERIFIED');
  assert.equal(task.claimed_by_agent, null);
  const event = db.prepare(
    "SELECT * FROM wisdomux_events WHERE event_type = 'TASK_RETRY_QUEUED'",
  ).get();
  assert.deepEqual(JSON.parse(event.payload_json), {
    attempt: 1,
    previous_state: 'BLOCKED',
    previous_truth_state: 'BLOCKED',
    reason: 'alternate adapter available',
  });
  assert.deepEqual(JSON.parse(event.evidence_json), [
    'recovery://adapter/loopback',
  ]);
});

test('does not bypass pending human approval', () => {
  const { db, recovery } = fixture({ approvalState: 'PENDING' });

  assert.throws(
    () => recovery.retry({
      taskId: 'task-1',
      requestedBy: 'coordinator-1',
      reason: 'approval still pending',
      evidenceRefs: ['recovery://pending'],
    }),
    /task approval does not allow retry/,
  );
  assert.equal(
    db.prepare("SELECT state FROM wisdomux_tasks WHERE task_id = 'task-1'").get().state,
    'BLOCKED',
  );
});

test('requires retry authority', () => {
  const { recovery } = fixture({ grants: ['observe'] });

  assert.throws(
    () => recovery.retry({
      taskId: 'task-1',
      requestedBy: 'coordinator-1',
      reason: 'unauthorized retry',
      evidenceRefs: ['recovery://unauthorized'],
    }),
    /missing capability: task.retry/,
  );
});

test('requires retry evidence', () => {
  const { recovery } = fixture();

  assert.throws(
    () => recovery.retry({
      taskId: 'task-1',
      requestedBy: 'coordinator-1',
      reason: 'no evidence',
      evidenceRefs: [],
    }),
    /at least one evidence reference is required/,
  );
});

test('stops requeueing after the configured attempt limit', () => {
  const { db, recovery } = fixture({ maxRetries: 2 });
  const insert = db.prepare(
    `INSERT INTO wisdomux_events
      (event_id, project_id, task_id, sender_agent, event_type,
       truth_state, payload_json, evidence_json, created_at)
     VALUES (?, 'wisdomux', 'task-1', 'coordinator-1',
             'TASK_RETRY_QUEUED', 'UNVERIFIED', ?, '[]', ?)`,
  );
  insert.run('prior-1', JSON.stringify({ attempt: 1 }), '2026-10-08T21:00:00Z');
  insert.run('prior-2', JSON.stringify({ attempt: 2 }), '2026-10-08T21:30:00Z');

  assert.throws(
    () => recovery.retry({
      taskId: 'task-1',
      requestedBy: 'coordinator-1',
      reason: 'too many attempts',
      evidenceRefs: ['recovery://limit'],
    }),
    /retry limit reached/,
  );
});

test('rolls back task state when retry evidence cannot be recorded', () => {
  const { db, recovery } = fixture({ newId: () => 'collision' });
  db.prepare(
    `INSERT INTO wisdomux_events
      (event_id, project_id, event_type, truth_state, created_at)
     VALUES ('collision', 'wisdomux', 'EXISTING', 'REAL', ?)`,
  ).run('2026-10-08T22:01:30.000Z');

  assert.throws(
    () => recovery.retry({
      taskId: 'task-1',
      requestedBy: 'coordinator-1',
      reason: 'must roll back',
      evidenceRefs: ['recovery://rollback'],
    }),
    /UNIQUE constraint failed/,
  );
  const task = db.prepare(
    "SELECT state, truth_state FROM wisdomux_tasks WHERE task_id = 'task-1'",
  ).get();
  assert.equal(task.state, 'BLOCKED');
  assert.equal(task.truth_state, 'BLOCKED');
});
