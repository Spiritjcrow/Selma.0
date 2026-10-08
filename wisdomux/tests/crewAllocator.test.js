'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { CrewAllocator } = require('../backend/crewAllocator');
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
     VALUES (?, ?, ?, ?, ?, ?)`,
  );
  const createdAt = '2026-10-08T14:00:00.000Z';
  insertAgent.run(
    'coordinator',
    'Coordinator',
    'Coordinator / PM',
    JSON.stringify({ grants: ['crew.assign'] }),
    'ONLINE',
    createdAt,
  );
  insertAgent.run(
    'backend-a',
    'Backend A',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    'ONLINE',
    createdAt,
  );
  insertAgent.run(
    'backend-b',
    'Backend B',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    'ONLINE',
    createdAt,
  );
  insertAgent.run(
    'backend-offline',
    'Backend Offline',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    'OFFLINE',
    createdAt,
  );
  const queue = new TaskQueue(db, {
    now: () => '2026-10-08T14:01:00.000Z',
  });
  const allocator = new CrewAllocator(db, {
    now: () => '2026-10-08T14:02:00.000Z',
    newId: () => 'event-assigned',
  });
  return { allocator, db, queue };
}

test('assigns the least-loaded matching online agent', () => {
  const { allocator, db, queue } = fixture();
  queue.enqueue({
    taskId: 'existing',
    projectId: 'wisdomux',
    title: 'Existing work',
    requiredCapability: 'task.execute',
  });
  db.prepare(
    `UPDATE wisdomux_tasks
        SET state = 'CLAIMED', claimed_by_agent = 'backend-a'
      WHERE task_id = 'existing'`,
  ).run();
  queue.enqueue({
    taskId: 'new-work',
    projectId: 'wisdomux',
    title: 'New work',
    requiredCapability: 'task.execute',
  });

  const assigned = allocator.assign({
    taskId: 'new-work',
    requestedBy: 'coordinator',
  });

  assert.equal(assigned.claimed_by_agent, 'backend-b');
  assert.equal(assigned.state, 'CLAIMED');
  const event = db.prepare(
    `SELECT sender_agent, payload_json
       FROM wisdomux_events
      WHERE event_type = 'CREW_ROLE_ASSIGNED'`,
  ).get();
  assert.equal(event.sender_agent, 'coordinator');
  assert.equal(JSON.parse(event.payload_json).assigned_agent, 'backend-b');
});

test('returns null when no online agent has the required capability', () => {
  const { allocator, db, queue } = fixture();
  queue.enqueue({
    taskId: 'specialized',
    projectId: 'wisdomux',
    title: 'Specialized work',
    requiredCapability: 'special.capability',
  });

  const assigned = allocator.assign({
    taskId: 'specialized',
    requestedBy: 'coordinator',
  });

  assert.equal(assigned, null);
  assert.equal(
    db.prepare(
      'SELECT state FROM wisdomux_tasks WHERE task_id = ?',
    ).get('specialized').state,
    'OBSERVED',
  );
});

test('rejects assignment by an agent without crew authority', () => {
  const { allocator, queue } = fixture();
  queue.enqueue({
    taskId: 'new-work',
    projectId: 'wisdomux',
    title: 'New work',
    requiredCapability: 'task.execute',
  });

  assert.throws(
    () =>
      allocator.assign({
        taskId: 'new-work',
        requestedBy: 'backend-a',
      }),
    /missing capability: crew.assign/,
  );
});

test('uses agent id as a deterministic tie breaker', () => {
  const { allocator, queue } = fixture();
  queue.enqueue({
    taskId: 'new-work',
    projectId: 'wisdomux',
    title: 'New work',
    requiredCapability: 'task.execute',
  });

  const assigned = allocator.assign({
    taskId: 'new-work',
    requestedBy: 'coordinator',
  });

  assert.equal(assigned.claimed_by_agent, 'backend-a');
});
