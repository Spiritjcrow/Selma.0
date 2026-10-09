'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { MaintenanceRunner } = require('../backend/maintenanceRunner');
const { TaskQueue } = require('../backend/taskQueue');

const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);

test('runs one local liveness and stale-task recovery cycle', () => {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration);
  const insertAgent = db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status,
       last_seen_at, created_at)
     VALUES (?, ?, ?, ?, 'ONLINE', ?, ?)`,
  );
  insertAgent.run(
    'coordinator-1',
    'Coordinator One',
    'Coordinator',
    JSON.stringify({ grants: ['agent.monitor', 'task.recover_stale'] }),
    '2026-10-09T04:00:00.000Z',
    '2026-10-09T03:00:00.000Z',
  );
  insertAgent.run(
    'stale-1',
    'Stale Worker',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    '2026-10-09T03:00:00.000Z',
    '2026-10-09T03:00:00.000Z',
  );
  insertAgent.run(
    'live-1',
    'Live Worker',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    '2026-10-09T03:59:00.000Z',
    '2026-10-09T03:00:00.000Z',
  );
  let id = 0;
  const queue = new TaskQueue(db, {
    now: () => '2026-10-09T03:10:00.000Z',
    newId: () => `queue-${++id}`,
  });
  for (const taskId of ['task-stale', 'task-live']) {
    queue.enqueue({
      taskId,
      projectId: 'wisdomux',
      title: taskId,
      requiredCapability: 'task.execute',
    });
  }
  db.prepare(
    `UPDATE wisdomux_tasks
        SET state = 'EXECUTING', claimed_by_agent = 'stale-1'
      WHERE task_id = 'task-stale'`,
  ).run();
  db.prepare(
    `UPDATE wisdomux_tasks
        SET state = 'EXECUTING', claimed_by_agent = 'live-1'
      WHERE task_id = 'task-live'`,
  ).run();
  const runner = new MaintenanceRunner(db, {
    now: () => '2026-10-09T04:00:00.000Z',
    newId: () => `maintenance-${++id}`,
  });

  const result = runner.runOnce({
    projectId: 'wisdomux',
    requestedBy: 'coordinator-1',
    cutoff: '2026-10-09T03:30:00.000Z',
  });

  assert.deepEqual(result, {
    cutoff: '2026-10-09T03:30:00.000Z',
    expiredAgents: ['stale-1'],
    recoveredTasks: ['task-stale'],
  });
  assert.deepEqual(
    {
      stale: db.prepare(
        "SELECT status FROM wisdomux_agents WHERE agent_id = 'stale-1'",
      ).get().status,
      live: db.prepare(
        "SELECT status FROM wisdomux_agents WHERE agent_id = 'live-1'",
      ).get().status,
      staleTask: db.prepare(
        "SELECT state FROM wisdomux_tasks WHERE task_id = 'task-stale'",
      ).get().state,
      liveTask: db.prepare(
        "SELECT state FROM wisdomux_tasks WHERE task_id = 'task-live'",
      ).get().state,
    },
    {
      stale: 'OFFLINE',
      live: 'ONLINE',
      staleTask: 'DEFERRED',
      liveTask: 'EXECUTING',
    },
  );
});
