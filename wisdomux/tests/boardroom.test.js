'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { Boardroom } = require('../backend/boardroom');
const { TaskQueue } = require('../backend/taskQueue');

const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);

function fixture() {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration);
  const insertAgent = db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, ?, ?, 'ONLINE', ?)`,
  );
  insertAgent.run(
    'coordinator',
    'Coordinator',
    'Coordinator / PM',
    JSON.stringify({ grants: ['boardroom.halt', 'boardroom.resume'] }),
    '2026-10-08T10:00:00.000Z',
  );
  insertAgent.run(
    'observer',
    'Observer',
    'Research',
    JSON.stringify({ grants: ['observe'] }),
    '2026-10-08T10:00:00.000Z',
  );
  const queue = new TaskQueue(db, {
    now: () => '2026-10-08T10:01:00.000Z',
    newId: () => 'event-enqueue',
  });
  queue.enqueue({
    taskId: 'task-1',
    projectId: 'wisdomux',
    title: 'Restore Boardroom',
  });
  let eventSequence = 0;
  const boardroom = new Boardroom(db, {
    now: () => '2026-10-08T10:02:00.000Z',
    newId: () => `event-boardroom-${++eventSequence}`,
  });
  return { boardroom, db };
}

test('authorized halt blocks only the selected task and records evidence', () => {
  const { boardroom, db } = fixture();

  const task = boardroom.halt({
    taskId: 'task-1',
    requestedBy: 'coordinator',
    reason: 'conflicting evidence',
    requiresHuman: true,
  });

  assert.equal(task.state, 'BLOCKED');
  assert.equal(task.truth_state, 'BLOCKED');
  assert.equal(task.approval_state, 'PENDING');
  const event = db.prepare(
    `SELECT event_type, sender_agent, payload_json
       FROM wisdomux_events
      WHERE event_type = 'BOARDROOM_HALTED'`,
  ).get();
  assert.equal(event.sender_agent, 'coordinator');
  assert.deepEqual(JSON.parse(event.payload_json), {
    previous_state: 'OBSERVED',
    reason: 'conflicting evidence',
    requires_human: true,
  });
});

test('agent without Boardroom capability cannot halt work', () => {
  const { boardroom } = fixture();

  assert.throws(
    () =>
      boardroom.halt({
        taskId: 'task-1',
        requestedBy: 'observer',
        reason: 'not authorized',
      }),
    /missing capability: boardroom.halt/,
  );
});

test('human-required halt cannot resume without approval', () => {
  const { boardroom, db } = fixture();
  boardroom.halt({
    taskId: 'task-1',
    requestedBy: 'coordinator',
    reason: 'needs decision',
    requiresHuman: true,
  });

  assert.throws(
    () =>
      boardroom.resume({
        taskId: 'task-1',
        resolvedBy: 'coordinator',
        resolution: 'attempted without approval',
      }),
    /human approval is required/,
  );
  assert.equal(
    db.prepare(
      'SELECT state FROM wisdomux_tasks WHERE task_id = ?',
    ).get('task-1').state,
    'BLOCKED',
  );
});

test('approved resolution safely requeues the task', () => {
  const { boardroom, db } = fixture();
  boardroom.halt({
    taskId: 'task-1',
    requestedBy: 'coordinator',
    reason: 'needs decision',
    requiresHuman: true,
  });

  const task = boardroom.resume({
    taskId: 'task-1',
    resolvedBy: 'coordinator',
    resolution: 'scope clarified',
    humanApproved: true,
  });

  assert.equal(task.state, 'DEFERRED');
  assert.equal(task.truth_state, 'UNVERIFIED');
  assert.equal(task.approval_state, 'APPROVED');
  assert.equal(task.claimed_by_agent, null);
  assert.equal(
    db.prepare(
      `SELECT COUNT(*) AS count
         FROM wisdomux_events
        WHERE event_type = 'BOARDROOM_RESUMED'`,
    ).get().count,
    1,
  );
});
