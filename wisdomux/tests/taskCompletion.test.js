'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { TaskCompletion } = require('../backend/taskCompletion');
const { TaskQueue } = require('../backend/taskQueue');

function migration(name) {
  return fs.readFileSync(
    path.join(__dirname, '..', 'db', 'migrations', name),
    'utf8',
  );
}

function fixture(options = {}) {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration('001_coordination_core.sql'));
  db.exec(migration('002_proof_ledger.sql'));
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, 'Backend', ?, 'ONLINE', ?)`,
  ).run(
    'backend-1',
    'Backend One',
    JSON.stringify({ grants: options.grants || ['task.execute', 'task.complete', 'proof.record'] }),
    '2026-10-08T18:00:00.000Z',
  );
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES ('other-1', 'Other One', 'Backend', ?, 'ONLINE', ?)`,
  ).run(
    JSON.stringify({ grants: ['task.execute', 'task.complete', 'proof.record'] }),
    '2026-10-08T18:00:00.000Z',
  );
  let id = 0;
  const queue = new TaskQueue(db, {
    now: () => '2026-10-08T18:01:00.000Z',
    newId: () => `queue-${++id}`,
  });
  queue.enqueue({
    taskId: 'task-1',
    projectId: 'wisdomux',
    title: 'Complete verified work',
    requiredCapability: 'task.execute',
  });
  queue.claimNext({ projectId: 'wisdomux', agentId: 'backend-1' });
  const completion = new TaskCompletion(db, {
    now: () => '2026-10-08T18:02:00.000Z',
    newId: options.newId || (() => `complete-${++id}`),
  });
  return { completion, db };
}

test('completes a claimed task with event evidence and chained proof', () => {
  const { completion, db } = fixture();

  const result = completion.complete({
    taskId: 'task-1',
    agentId: 'backend-1',
    claim: 'all 28 tests passed',
    truthState: 'REAL',
    evidenceRefs: ['test://local/28-pass'],
  });

  assert.equal(result.task.state, 'COMPLETED');
  assert.equal(result.task.truth_state, 'REAL');
  assert.equal(result.proof.task_id, 'task-1');
  assert.equal(result.proof.claim, 'all 28 tests passed');
  assert.deepEqual(JSON.parse(result.proof.evidence_json), ['test://local/28-pass']);
  const event = db.prepare(
    "SELECT * FROM wisdomux_events WHERE event_type = 'TASK_COMPLETED'",
  ).get();
  assert.deepEqual(JSON.parse(event.evidence_json), ['test://local/28-pass']);
});

test('rejects completion by an agent that does not own the claim', () => {
  const { completion, db } = fixture();

  assert.throws(
    () => completion.complete({
      taskId: 'task-1',
      agentId: 'other-1',
      claim: 'not my task',
      truthState: 'REAL',
      evidenceRefs: ['test://other'],
    }),
    /task is not claimed by agent/,
  );
  assert.equal(
    db.prepare("SELECT state FROM wisdomux_tasks WHERE task_id = 'task-1'").get().state,
    'CLAIMED',
  );
});

test('requires completion evidence', () => {
  const { completion } = fixture();

  assert.throws(
    () => completion.complete({
      taskId: 'task-1',
      agentId: 'backend-1',
      claim: 'unsupported completion',
      truthState: 'REAL',
      evidenceRefs: [],
    }),
    /at least one evidence reference is required/,
  );
});

test('requires task completion authority', () => {
  const { completion } = fixture({ grants: ['task.execute', 'proof.record'] });

  assert.throws(
    () => completion.complete({
      taskId: 'task-1',
      agentId: 'backend-1',
      claim: 'not authorized to complete',
      truthState: 'REAL',
      evidenceRefs: ['test://authority'],
    }),
    /missing capability: task.complete/,
  );
});

test('requires proof recording authority', () => {
  const { completion } = fixture({ grants: ['task.execute', 'task.complete'] });

  assert.throws(
    () => completion.complete({
      taskId: 'task-1',
      agentId: 'backend-1',
      claim: 'cannot record proof',
      truthState: 'REAL',
      evidenceRefs: ['test://proof-authority'],
    }),
    /missing capability: proof.record/,
  );
});

test('rolls back task state when completion evidence cannot be recorded', () => {
  const { completion, db } = fixture({ newId: () => 'collision' });
  db.prepare(
    `INSERT INTO wisdomux_events
      (event_id, project_id, event_type, truth_state, created_at)
     VALUES ('collision', 'wisdomux', 'EXISTING', 'REAL', ?)`,
  ).run('2026-10-08T18:01:30.000Z');

  assert.throws(
    () => completion.complete({
      taskId: 'task-1',
      agentId: 'backend-1',
      claim: 'must roll back',
      truthState: 'REAL',
      evidenceRefs: ['test://rollback'],
    }),
    /UNIQUE constraint failed/,
  );
  assert.equal(
    db.prepare("SELECT state FROM wisdomux_tasks WHERE task_id = 'task-1'").get().state,
    'CLAIMED',
  );
  assert.equal(
    db.prepare('SELECT COUNT(*) AS count FROM wisdomux_proof_ledger').get().count,
    0,
  );
});
