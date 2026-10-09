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

test('previews the bounded maintenance impact without changing the database', () => {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration);
  const insertAgent = db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status,
       last_seen_at, created_at)
     VALUES (?, ?, 'Backend', ?, ?, ?, '2026-10-09T03:00:00.000Z')`,
  );
  insertAgent.run(
    'coordinator-1',
    'Coordinator',
    JSON.stringify({ grants: ['agent.monitor', 'task.recover_stale'] }),
    'ONLINE',
    '2026-10-09T04:59:00.000Z',
  );
  insertAgent.run(
    'stale-1',
    'Stale Worker',
    JSON.stringify({ grants: ['task.execute'] }),
    'BUSY',
    '2026-10-09T04:00:00.000Z',
  );
  insertAgent.run(
    'revoked-1',
    'Revoked Worker',
    JSON.stringify({ grants: ['task.execute'] }),
    'REVOKED',
    '2026-10-09T04:59:00.000Z',
  );
  insertAgent.run(
    'live-1',
    'Live Worker',
    JSON.stringify({ grants: ['task.execute'] }),
    'ONLINE',
    '2026-10-09T04:59:00.000Z',
  );
  const insertTask = db.prepare(
    `INSERT INTO wisdomux_tasks
      (task_id, project_id, title, state, truth_state, priority,
       claimed_by_agent, approval_state, created_at, updated_at)
     VALUES (?, ?, ?, 'EXECUTING', ?, ?, ?, ?,
             '2026-10-09T04:10:00.000Z', ?)`,
  );
  insertTask.run(
    'task-stale', 'wisdomux', 'Stale task', 'INFERRED', 80, 'stale-1',
    'APPROVED', '2026-10-09T04:20:00.000Z',
  );
  insertTask.run(
    'task-revoked', 'wisdomux', 'Revoked task', 'REAL', 90, 'revoked-1',
    'PENDING', '2026-10-09T04:21:00.000Z',
  );
  insertTask.run(
    'task-live', 'wisdomux', 'Live task', 'REAL', 100, 'live-1',
    'NOT_REQUIRED', '2026-10-09T04:22:00.000Z',
  );
  insertTask.run(
    'task-other', 'other', 'Other project', 'REAL', 100, 'stale-1',
    'NOT_REQUIRED', '2026-10-09T04:23:00.000Z',
  );
  const before = JSON.stringify({
    agents: db.prepare('SELECT * FROM wisdomux_agents ORDER BY agent_id').all(),
    tasks: db.prepare('SELECT * FROM wisdomux_tasks ORDER BY task_id').all(),
    events: db.prepare('SELECT * FROM wisdomux_events ORDER BY event_id').all(),
  });
  const runner = new MaintenanceRunner(db, { sweepLimit: 2 });

  const result = runner.previewOnce({
    projectId: 'wisdomux',
    requestedBy: 'coordinator-1',
    cutoff: '2026-10-09T04:30:00Z',
  });

  assert.deepEqual(result, {
    truthState: 'PREVIEW',
    ready: true,
    blockers: [],
    projectId: 'wisdomux',
    cutoff: '2026-10-09T04:30:00.000Z',
    sweepLimit: 2,
    expiredAgents: [
      {
        agentId: 'stale-1',
        previousStatus: 'BUSY',
        lastSeenAt: '2026-10-09T04:00:00.000Z',
      },
    ],
    recoveredTasks: [
      {
        taskId: 'task-revoked',
        previousOwner: 'revoked-1',
        currentOwnerStatus: 'REVOKED',
        projectedOwnerStatus: 'REVOKED',
        previousState: 'EXECUTING',
        previousTruthState: 'REAL',
        approvalState: 'PENDING',
      },
      {
        taskId: 'task-stale',
        previousOwner: 'stale-1',
        currentOwnerStatus: 'BUSY',
        projectedOwnerStatus: 'OFFLINE',
        previousState: 'EXECUTING',
        previousTruthState: 'INFERRED',
        approvalState: 'APPROVED',
      },
    ],
  });
  assert.equal(JSON.stringify({
    agents: db.prepare('SELECT * FROM wisdomux_agents ORDER BY agent_id').all(),
    tasks: db.prepare('SELECT * FROM wisdomux_tasks ORDER BY task_id').all(),
    events: db.prepare('SELECT * FROM wisdomux_events ORDER BY event_id').all(),
  }), before);
});

test('requires both maintenance capabilities before previewing impact', () => {
  const db = new DatabaseSync(':memory:');
  db.exec(migration);
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES ('coordinator-1', 'Coordinator', 'Coordinator', ?, 'ONLINE', ?)`,
  ).run(
    JSON.stringify({ grants: ['agent.monitor'] }),
    '2026-10-09T03:00:00.000Z',
  );
  const runner = new MaintenanceRunner(db);

  assert.throws(() => runner.previewOnce({
    projectId: 'wisdomux',
    requestedBy: 'coordinator-1',
    cutoff: '2026-10-09T04:30:00Z',
  }), /missing capability: task.recover_stale/);
});

test('blocks a run whose cutoff would expire its coordinator', () => {
  const db = new DatabaseSync(':memory:');
  db.exec(migration);
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status,
       last_seen_at, created_at)
     VALUES ('coordinator-1', 'Coordinator', 'Coordinator', ?, 'ONLINE', ?, ?)`,
  ).run(
    JSON.stringify({ grants: ['agent.monitor', 'task.recover_stale'] }),
    '2026-10-09T04:00:00.000Z',
    '2026-10-09T03:00:00.000Z',
  );
  const runner = new MaintenanceRunner(db);

  const result = runner.previewOnce({
    projectId: 'wisdomux',
    requestedBy: 'coordinator-1',
    cutoff: '2026-10-09T04:30:00Z',
  });

  assert.equal(result.ready, false);
  assert.deepEqual(result.blockers, [
    'coordinator would be marked offline before task recovery',
  ]);
});

test('rejects coordinator self-expiry before maintenance changes any rows', () => {
  const db = new DatabaseSync(':memory:');
  db.exec(migration);
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status,
       last_seen_at, created_at)
     VALUES ('coordinator-1', 'Coordinator', 'Coordinator', ?, 'ONLINE', ?, ?)`,
  ).run(
    JSON.stringify({ grants: ['agent.monitor', 'task.recover_stale'] }),
    '2026-10-09T04:00:00.000Z',
    '2026-10-09T03:00:00.000Z',
  );
  const before = JSON.stringify({
    agents: db.prepare('SELECT * FROM wisdomux_agents').all(),
    tasks: db.prepare('SELECT * FROM wisdomux_tasks').all(),
    events: db.prepare('SELECT * FROM wisdomux_events').all(),
  });
  const runner = new MaintenanceRunner(db);

  assert.throws(() => runner.runOnce({
    projectId: 'wisdomux',
    requestedBy: 'coordinator-1',
    cutoff: '2026-10-09T04:30:00Z',
  }), /coordinator would be marked offline before task recovery/);
  assert.equal(JSON.stringify({
    agents: db.prepare('SELECT * FROM wisdomux_agents').all(),
    tasks: db.prepare('SELECT * FROM wisdomux_tasks').all(),
    events: db.prepare('SELECT * FROM wisdomux_events').all(),
  }), before);
});
