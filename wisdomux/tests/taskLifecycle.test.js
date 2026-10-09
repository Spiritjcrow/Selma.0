'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { TaskLifecycle } = require('../backend/taskLifecycle');
const { TaskQueue } = require('../backend/taskQueue');

const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);

const ALL_GRANTS = [
  'task.execute',
  'task.plan',
  'task.report',
  'task.verify',
];

function fixture(options = {}) {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration);
  const insertAgent = db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, 'Builder', ?, 'ONLINE', ?)`,
  );
  insertAgent.run(
    'builder-1',
    'Builder One',
    JSON.stringify({ grants: options.grants || ALL_GRANTS }),
    '2026-10-09T00:00:00.000Z',
  );
  insertAgent.run(
    'builder-2',
    'Builder Two',
    JSON.stringify({ grants: ALL_GRANTS }),
    '2026-10-09T00:00:00.000Z',
  );
  let id = 0;
  const queue = new TaskQueue(db, {
    now: () => '2026-10-09T00:01:00.000Z',
    newId: () => `queue-${++id}`,
  });
  queue.enqueue({
    taskId: 'task-1',
    projectId: 'wisdomux',
    title: 'Advance controlled work',
    requiredCapability: 'task.execute',
    approvalState: options.approvalState || 'NOT_REQUIRED',
  });
  queue.claimNext({ projectId: 'wisdomux', agentId: 'builder-1' });
  const lifecycle = new TaskLifecycle(db, {
    now: () => '2026-10-09T00:02:00.000Z',
    newId: options.newId || (() => `lifecycle-${++id}`),
  });
  return { db, lifecycle };
}

function transition(lifecycle, toState, suffix = toState.toLowerCase()) {
  return lifecycle.transition({
    taskId: 'task-1',
    agentId: 'builder-1',
    toState,
    summary: `advanced to ${toState}`,
    evidenceRefs: [`test://lifecycle/${suffix}`],
  });
}

test('advances the owner through the controlled lifecycle with evidence', () => {
  const { db, lifecycle } = fixture();

  for (const state of ['PLANNED', 'EXECUTING', 'VERIFYING', 'REPORTED']) {
    assert.equal(transition(lifecycle, state).state, state);
  }

  const events = db.prepare(
    `SELECT * FROM wisdomux_events
      WHERE event_type = 'TASK_STATE_TRANSITIONED'
      ORDER BY rowid`,
  ).all();
  assert.equal(events.length, 4);
  assert.deepEqual(JSON.parse(events[0].payload_json), {
    from_state: 'CLAIMED',
    to_state: 'PLANNED',
    summary: 'advanced to PLANNED',
  });
  assert.deepEqual(JSON.parse(events[3].evidence_json), [
    'test://lifecycle/reported',
  ]);
});

test('rejects skipped or backward lifecycle states', () => {
  const { db, lifecycle } = fixture();

  assert.throws(
    () => transition(lifecycle, 'EXECUTING'),
    /invalid lifecycle transition: CLAIMED -> EXECUTING/,
  );
  assert.equal(
    db.prepare("SELECT state FROM wisdomux_tasks WHERE task_id = 'task-1'").get().state,
    'CLAIMED',
  );
});

test('rejects a lifecycle transition by an agent that does not own the task', () => {
  const { lifecycle } = fixture();

  assert.throws(
    () => lifecycle.transition({
      taskId: 'task-1',
      agentId: 'builder-2',
      toState: 'PLANNED',
      summary: 'take over task',
      evidenceRefs: ['test://lifecycle/other-owner'],
    }),
    /task is not claimed by agent/,
  );
});

test('requires the capability assigned to each lifecycle stage', () => {
  const { lifecycle } = fixture({
    grants: ['task.execute', 'task.plan', 'task.report'],
  });
  transition(lifecycle, 'PLANNED');
  transition(lifecycle, 'EXECUTING');

  assert.throws(
    () => transition(lifecycle, 'VERIFYING'),
    /missing capability: task.verify/,
  );
});

test('does not enter execution while approval is pending', () => {
  const { db, lifecycle } = fixture({ approvalState: 'PENDING' });
  transition(lifecycle, 'PLANNED');

  assert.throws(
    () => transition(lifecycle, 'EXECUTING'),
    /task approval does not allow execution/,
  );
  assert.equal(
    db.prepare("SELECT state FROM wisdomux_tasks WHERE task_id = 'task-1'").get().state,
    'PLANNED',
  );
});

test('requires evidence for every lifecycle transition', () => {
  const { lifecycle } = fixture();

  assert.throws(
    () => lifecycle.transition({
      taskId: 'task-1',
      agentId: 'builder-1',
      toState: 'PLANNED',
      summary: 'unsupported plan',
      evidenceRefs: [],
    }),
    /at least one evidence reference is required/,
  );
});

test('rolls back task state when transition evidence cannot be recorded', () => {
  const { db, lifecycle } = fixture({ newId: () => 'collision' });
  db.prepare(
    `INSERT INTO wisdomux_events
      (event_id, project_id, event_type, truth_state, created_at)
     VALUES ('collision', 'wisdomux', 'EXISTING', 'REAL', ?)`,
  ).run('2026-10-09T00:01:30.000Z');

  assert.throws(
    () => transition(lifecycle, 'PLANNED'),
    /UNIQUE constraint failed/,
  );
  assert.equal(
    db.prepare("SELECT state FROM wisdomux_tasks WHERE task_id = 'task-1'").get().state,
    'CLAIMED',
  );
});
