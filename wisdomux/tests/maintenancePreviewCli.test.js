'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const cli = path.join(__dirname, '..', 'bin', 'maintenancePreview.js');
const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);

function createFixture(databasePath, coordinatorLastSeen = '2026-10-09T04:59:00.000Z') {
  const db = new DatabaseSync(databasePath);
  db.exec(migration);
  const insertAgent = db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status,
       last_seen_at, created_at)
     VALUES (?, ?, ?, ?, ?, ?, '2026-10-09T03:00:00.000Z')`,
  );
  insertAgent.run(
    'coordinator-1', 'Coordinator', 'Coordinator',
    JSON.stringify({ grants: ['agent.monitor', 'task.recover_stale'] }),
    'ONLINE', coordinatorLastSeen,
  );
  insertAgent.run(
    'stale-1', 'Stale Worker', 'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    'ONLINE', '2026-10-09T04:00:00.000Z',
  );
  db.prepare(
    `INSERT INTO wisdomux_tasks
      (task_id, project_id, title, state, truth_state, priority,
       claimed_by_agent, approval_state, created_at, updated_at)
     VALUES ('task-stale', 'wisdomux', 'Stale task', 'EXECUTING',
             'INFERRED', 80, 'stale-1', 'APPROVED', ?, ?)`,
  ).run('2026-10-09T04:10:00.000Z', '2026-10-09T04:20:00.000Z');
  db.close();
}

function snapshot(databasePath) {
  const db = new DatabaseSync(databasePath, { readOnly: true });
  const rows = {
    agents: db.prepare('SELECT * FROM wisdomux_agents ORDER BY agent_id').all(),
    tasks: db.prepare('SELECT * FROM wisdomux_tasks ORDER BY task_id').all(),
    events: db.prepare('SELECT * FROM wisdomux_events ORDER BY event_id').all(),
  };
  db.close();
  return JSON.stringify(rows);
}

test('prints a read-only maintenance impact preview', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-preview-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath);
    const before = snapshot(databasePath);

    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--project', 'wisdomux',
      '--coordinator', 'coordinator-1',
      '--cutoff', '2026-10-09T04:30:00Z',
      '--sweep-limit', '25',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, '');
    assert.deepEqual(JSON.parse(result.stdout), {
      truthState: 'PREVIEW',
      ready: true,
      blockers: [],
      projectId: 'wisdomux',
      cutoff: '2026-10-09T04:30:00.000Z',
      sweepLimit: 25,
      expiredAgents: [
        {
          agentId: 'stale-1',
          previousStatus: 'ONLINE',
          lastSeenAt: '2026-10-09T04:00:00.000Z',
        },
      ],
      recoveredTasks: [
        {
          taskId: 'task-stale',
          previousOwner: 'stale-1',
          currentOwnerStatus: 'ONLINE',
          projectedOwnerStatus: 'OFFLINE',
          previousState: 'EXECUTING',
          previousTruthState: 'INFERRED',
          approvalState: 'APPROVED',
        },
      ],
    });
    assert.equal(snapshot(databasePath), before);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('returns blocked when the cutoff would expire the coordinator', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-preview-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath, '2026-10-09T04:00:00.000Z');

    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--project', 'wisdomux',
      '--coordinator', 'coordinator-1',
      '--cutoff', '2026-10-09T04:30:00Z',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 2);
    assert.equal(result.stderr, '');
    const report = JSON.parse(result.stdout);
    assert.equal(report.ready, false);
    assert.deepEqual(report.blockers, [
      'coordinator would be marked offline before task recovery',
    ]);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
