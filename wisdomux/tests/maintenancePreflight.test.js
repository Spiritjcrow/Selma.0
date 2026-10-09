'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');
const { evaluateIntegrity } = require('../bin/maintenancePreflight');

const cli = path.join(__dirname, '..', 'bin', 'maintenancePreflight.js');
const migrationDirectory = path.join(__dirname, '..', 'db', 'migrations');

test('treats every non-ok integrity result as a readiness blocker', () => {
  assert.deepEqual(evaluateIntegrity([
    { integrity_check: 'row 17 missing from index task_state_idx' },
  ]), {
    status: 'failed',
    blocker: 'database integrity check failed',
  });
});

function createFixture(databasePath, grants = [
  'agent.monitor',
  'task.recover_stale',
], status = 'ONLINE') {
  const db = new DatabaseSync(databasePath);
  db.exec('PRAGMA foreign_keys = ON');
  for (const migration of [
    '001_coordination_core.sql',
    '002_proof_ledger.sql',
  ]) {
    db.exec(fs.readFileSync(path.join(migrationDirectory, migration), 'utf8'));
  }
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status,
       last_seen_at, created_at)
     VALUES ('coordinator-1', 'Coordinator One', 'Coordinator', ?, ?,
             '2026-10-09T16:00:00.000Z', '2026-10-09T15:00:00.000Z')`,
  ).run(JSON.stringify({ grants }), status);
  db.close();
}

function counts(databasePath) {
  const db = new DatabaseSync(databasePath, { readOnly: true });
  const result = {};
  for (const table of [
    'wisdomux_agents',
    'wisdomux_tasks',
    'wisdomux_events',
    'wisdomux_proof_ledger',
  ]) {
    result[table] = db.prepare(`SELECT COUNT(*) AS count FROM ${table}`).get().count;
  }
  db.close();
  return result;
}

test('reports a ready maintenance database without changing it', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-preflight-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath);
    const before = counts(databasePath);

    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--coordinator', 'coordinator-1',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, '');
    assert.deepEqual(JSON.parse(result.stdout), {
      ready: true,
      database: databasePath,
      coordinator: {
        agentId: 'coordinator-1',
        status: 'ONLINE',
        grants: ['agent.monitor', 'task.recover_stale'],
      },
      checks: {
        schema: 'ok',
        integrity: 'ok',
        foreignKeys: 'ok',
      },
      blockers: [],
    });
    assert.deepEqual(counts(databasePath), before);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('reports a missing maintenance capability as a blocker', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-preflight-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath, ['agent.monitor']);

    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--coordinator', 'coordinator-1',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 2);
    assert.equal(result.stderr, '');
    const report = JSON.parse(result.stdout);
    assert.equal(report.ready, false);
    assert.deepEqual(report.blockers, [
      'missing capability: task.recover_stale',
    ]);
    assert.deepEqual(report.coordinator.grants, ['agent.monitor']);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('reports an unavailable coordinator as a blocker', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-preflight-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(
      databasePath,
      ['agent.monitor', 'task.recover_stale'],
      'OFFLINE',
    );

    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--coordinator', 'coordinator-1',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 2);
    assert.equal(result.stderr, '');
    const report = JSON.parse(result.stdout);
    assert.equal(report.ready, false);
    assert.deepEqual(report.blockers, [
      'coordinator status is not available: OFFLINE',
    ]);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('reports a missing canonical table as a blocker', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-preflight-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath);
    const damaged = new DatabaseSync(databasePath);
    damaged.exec('DROP TABLE wisdomux_proof_ledger');
    damaged.close();

    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--coordinator', 'coordinator-1',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 2);
    assert.equal(result.stderr, '');
    const report = JSON.parse(result.stdout);
    assert.equal(report.ready, false);
    assert.equal(report.checks.schema, 'failed');
    assert.deepEqual(report.blockers, [
      'missing table: wisdomux_proof_ledger',
    ]);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('reports foreign-key violations as a blocker', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-preflight-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    createFixture(databasePath);
    const damaged = new DatabaseSync(databasePath);
    damaged.exec('PRAGMA foreign_keys = OFF');
    damaged.prepare(
      `INSERT INTO wisdomux_tasks
        (task_id, project_id, title, state, truth_state, claimed_by_agent,
         created_at, updated_at)
       VALUES ('task-invalid', 'wisdomux', 'Invalid owner', 'CLAIMED',
               'UNVERIFIED', 'missing-agent', ?, ?)`,
    ).run('2026-10-09T16:00:00.000Z', '2026-10-09T16:00:00.000Z');
    damaged.close();

    const result = spawnSync(process.execPath, [
      cli,
      '--db', databasePath,
      '--coordinator', 'coordinator-1',
    ], { encoding: 'utf8' });

    assert.equal(result.status, 2);
    assert.equal(result.stderr, '');
    const report = JSON.parse(result.stdout);
    assert.equal(report.ready, false);
    assert.equal(report.checks.foreignKeys, 'failed');
    assert.deepEqual(report.blockers, ['foreign key violations: 1']);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
