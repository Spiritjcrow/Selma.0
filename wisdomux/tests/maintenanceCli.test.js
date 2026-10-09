'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { TaskQueue } = require('../backend/taskQueue');

const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);
const cli = path.join(__dirname, '..', 'bin', 'maintenance.js');
const termuxLauncher = path.join(
  __dirname,
  '..',
  'bin',
  'maintenance-termux.sh',
);

function createFixture(databasePath) {
  const db = new DatabaseSync(databasePath);
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
    '2026-10-09T05:00:00.000Z',
    '2026-10-09T04:00:00.000Z',
  );
  insertAgent.run(
    'stale-1',
    'Stale Worker',
    'Backend',
    JSON.stringify({ grants: ['task.execute'] }),
    '2026-10-09T04:00:00.000Z',
    '2026-10-09T04:00:00.000Z',
  );
  const queue = new TaskQueue(db, {
    now: () => '2026-10-09T04:10:00.000Z',
    newId: () => 'queue-event-1',
  });
  queue.enqueue({
    taskId: 'task-stale',
    projectId: 'wisdomux',
    title: 'Recover stale task',
    requiredCapability: 'task.execute',
  });
  db.prepare(
    `UPDATE wisdomux_tasks
        SET state = 'EXECUTING', claimed_by_agent = 'stale-1'
      WHERE task_id = 'task-stale'`,
  ).run();
  db.close();
}

test('runs one maintenance cycle against an explicit local database', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-cli-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath);

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
      cutoff: '2026-10-09T04:30:00.000Z',
      expiredAgents: ['stale-1'],
      recoveredTasks: ['task-stale'],
    });
    const db = new DatabaseSync(databasePath, { readOnly: true });
    assert.equal(
      db.prepare("SELECT status FROM wisdomux_agents WHERE agent_id = 'stale-1'").get().status,
      'OFFLINE',
    );
    assert.deepEqual(
      { ...db.prepare(
        "SELECT state, claimed_by_agent FROM wisdomux_tasks WHERE task_id = 'task-stale'",
      ).get() },
      { state: 'DEFERRED', claimed_by_agent: null },
    );
    db.close();
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('refuses a missing database without creating it', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-cli-'));
  const databasePath = path.join(directory, 'missing.sqlite');
  try {
    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--project', 'wisdomux',
      '--coordinator', 'coordinator-1',
      '--cutoff', '2026-10-09T04:30:00Z',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 1);
    assert.match(result.stderr, /database does not exist/);
    assert.equal(result.stdout, '');
    assert.equal(fs.existsSync(databasePath), false);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('Termux launcher forwards the maintenance arguments', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-cli-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath);

    const result = spawnSync('/bin/sh', [
      termuxLauncher,
      '--db', databasePath,
      '--project', 'wisdomux',
      '--coordinator', 'coordinator-1',
      '--cutoff', '2026-10-09T04:30:00Z',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, '');
    assert.deepEqual(JSON.parse(result.stdout), {
      cutoff: '2026-10-09T04:30:00.000Z',
      expiredAgents: ['stale-1'],
      recoveredTasks: ['task-stale'],
    });
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
