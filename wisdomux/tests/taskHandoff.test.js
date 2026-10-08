'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { TaskHandoff } = require('../backend/taskHandoff');
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
     VALUES (?, ?, 'Backend', ?, ?, ?)`,
  );
  insertAgent.run(
    'source-1',
    'Source One',
    JSON.stringify({ grants: ['task.execute', 'task.handoff'] }),
    'ONLINE',
    '2026-10-08T20:00:00.000Z',
  );
  insertAgent.run(
    'target-1',
    'Target One',
    JSON.stringify({ grants: ['task.execute', 'task.handoff'] }),
    options.targetStatus || 'ONLINE',
    '2026-10-08T20:00:00.000Z',
  );
  insertAgent.run(
    'observer-1',
    'Observer One',
    JSON.stringify({ grants: ['observe'] }),
    'ONLINE',
    '2026-10-08T20:00:00.000Z',
  );
  let id = 0;
  const queue = new TaskQueue(db, {
    now: () => '2026-10-08T20:01:00.000Z',
    newId: () => `queue-${++id}`,
  });
  queue.enqueue({
    taskId: 'task-1',
    projectId: 'wisdomux',
    title: 'Transfer owned work',
    requiredCapability: 'task.execute',
  });
  queue.claimNext({ projectId: 'wisdomux', agentId: 'source-1' });
  const handoff = new TaskHandoff(db, {
    now: () => '2026-10-08T20:02:00.000Z',
    newId: options.newId || (() => `handoff-${++id}`),
  });
  return { db, handoff };
}

test('transfers a claimed task to an eligible agent with evidence', () => {
  const { db, handoff } = fixture();

  const task = handoff.transfer({
    taskId: 'task-1',
    fromAgent: 'source-1',
    toAgent: 'target-1',
    reason: 'specialist continuation',
    evidenceRefs: ['handoff://context/1'],
  });

  assert.equal(task.state, 'CLAIMED');
  assert.equal(task.claimed_by_agent, 'target-1');
  const event = db.prepare(
    "SELECT * FROM wisdomux_events WHERE event_type = 'TASK_HANDED_OFF'",
  ).get();
  assert.deepEqual(JSON.parse(event.payload_json), {
    from_agent: 'source-1',
    to_agent: 'target-1',
    reason: 'specialist continuation',
  });
  assert.deepEqual(JSON.parse(event.evidence_json), ['handoff://context/1']);
});

test('rejects handoff by an agent that does not own the task', () => {
  const { db, handoff } = fixture();

  assert.throws(
    () => handoff.transfer({
      taskId: 'task-1',
      fromAgent: 'target-1',
      toAgent: 'observer-1',
      reason: 'invalid transfer',
      evidenceRefs: ['handoff://invalid'],
    }),
    /task is not claimed by source agent/,
  );
  assert.equal(
    db.prepare("SELECT claimed_by_agent FROM wisdomux_tasks WHERE task_id = 'task-1'").get().claimed_by_agent,
    'source-1',
  );
});

test('rejects a target missing the task capability', () => {
  const { db, handoff } = fixture();

  assert.throws(
    () => handoff.transfer({
      taskId: 'task-1',
      fromAgent: 'source-1',
      toAgent: 'observer-1',
      reason: 'wrong specialist',
      evidenceRefs: ['handoff://capability'],
    }),
    /target missing capability: task.execute/,
  );
  assert.equal(
    db.prepare("SELECT claimed_by_agent FROM wisdomux_tasks WHERE task_id = 'task-1'").get().claimed_by_agent,
    'source-1',
  );
});

test('rejects an unavailable handoff target', () => {
  const { handoff } = fixture({ targetStatus: 'OFFLINE' });

  assert.throws(
    () => handoff.transfer({
      taskId: 'task-1',
      fromAgent: 'source-1',
      toAgent: 'target-1',
      reason: 'offline transfer',
      evidenceRefs: ['handoff://offline'],
    }),
    /target agent is not available/,
  );
});

test('requires handoff evidence', () => {
  const { handoff } = fixture();

  assert.throws(
    () => handoff.transfer({
      taskId: 'task-1',
      fromAgent: 'source-1',
      toAgent: 'target-1',
      reason: 'no evidence',
      evidenceRefs: [],
    }),
    /at least one evidence reference is required/,
  );
});

test('rolls back ownership when handoff evidence cannot be recorded', () => {
  const { db, handoff } = fixture({ newId: () => 'collision' });
  db.prepare(
    `INSERT INTO wisdomux_events
      (event_id, project_id, event_type, truth_state, created_at)
     VALUES ('collision', 'wisdomux', 'EXISTING', 'REAL', ?)`,
  ).run('2026-10-08T20:01:30.000Z');

  assert.throws(
    () => handoff.transfer({
      taskId: 'task-1',
      fromAgent: 'source-1',
      toAgent: 'target-1',
      reason: 'must roll back',
      evidenceRefs: ['handoff://rollback'],
    }),
    /UNIQUE constraint failed/,
  );
  assert.equal(
    db.prepare("SELECT claimed_by_agent FROM wisdomux_tasks WHERE task_id = 'task-1'").get().claimed_by_agent,
    'source-1',
  );
});
