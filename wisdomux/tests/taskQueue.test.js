'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { TaskQueue } = require('../backend/taskQueue');

const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);

function fixture() {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration);
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, ?, ?, 'ONLINE', ?)`,
  ).run(
    'sol-blue',
    'Sol Blue',
    'Security',
    JSON.stringify({ grants: ['observe', 'verify'] }),
    '2026-10-08T06:00:00.000Z',
  );
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, ?, ?, 'ONLINE', ?)`,
  ).run(
    'backend-1',
    'Backend One',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    '2026-10-08T06:00:00.000Z',
  );
  const queue = new TaskQueue(db, {
    now: () => '2026-10-08T06:01:00.000Z',
  });
  return { db, queue };
}

test('claims the highest-priority eligible task', () => {
  const { db, queue } = fixture();
  queue.enqueue({
    taskId: 'low',
    projectId: 'wisdomux',
    title: 'Low priority',
    priority: 10,
  });
  queue.enqueue({
    taskId: 'high',
    projectId: 'wisdomux',
    title: 'High priority',
    priority: 90,
    requiredCapability: 'task.execute',
  });

  const claimed = queue.claimNext({
    projectId: 'wisdomux',
    agentId: 'backend-1',
  });

  assert.equal(claimed.task_id, 'high');
  assert.equal(claimed.state, 'CLAIMED');
  assert.equal(claimed.claimed_by_agent, 'backend-1');
  assert.equal(
    db.prepare('SELECT COUNT(*) AS count FROM wisdomux_events').get().count,
    3,
  );
});

test('does not claim a task with an unfinished dependency', () => {
  const { queue } = fixture();
  queue.enqueue({
    taskId: 'foundation',
    projectId: 'wisdomux',
    title: 'Foundation',
    priority: 20,
  });
  queue.enqueue({
    taskId: 'dependent',
    projectId: 'wisdomux',
    title: 'Dependent',
    priority: 100,
    dependencies: ['foundation'],
  });

  const claimed = queue.claimNext({
    projectId: 'wisdomux',
    agentId: 'backend-1',
  });

  assert.equal(claimed.task_id, 'foundation');
});

test('derives capability eligibility from the registered agent', () => {
  const { queue } = fixture();
  queue.enqueue({
    taskId: 'execute',
    projectId: 'wisdomux',
    title: 'Execute',
    requiredCapability: 'task.execute',
  });

  const claimed = queue.claimNext({
    projectId: 'wisdomux',
    agentId: 'sol-blue',
  });

  assert.equal(claimed, null);
});

test('rejects claims from offline agents', () => {
  const { db, queue } = fixture();
  queue.enqueue({
    taskId: 'work',
    projectId: 'wisdomux',
    title: 'Work',
  });
  db.prepare(
    "UPDATE wisdomux_agents SET status = 'OFFLINE' WHERE agent_id = ?",
  ).run('backend-1');

  assert.throws(
    () =>
      queue.claimNext({
        projectId: 'wisdomux',
        agentId: 'backend-1',
      }),
    /agent is not available/,
  );
});
