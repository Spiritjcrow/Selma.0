'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const cli = path.join(__dirname, '..', 'bin', 'initializeDatabase.js');

test('creates an empty database from the canonical migrations', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-init-'));
  const databasePath = path.join(directory, 'coordination.sqlite');
  try {
    const result = spawnSync(process.execPath, [cli, '--db', databasePath], {
      encoding: 'utf8',
    });

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, '');
    assert.deepEqual(JSON.parse(result.stdout), {
      database: databasePath,
      migrations: [
        '001_coordination_core.sql',
        '002_proof_ledger.sql',
      ],
    });
    const db = new DatabaseSync(databasePath, { readOnly: true });
    const tables = new Set(db.prepare(
      "SELECT name FROM sqlite_master WHERE type = 'table'",
    ).all().map((row) => row.name));
    assert.equal(tables.has('wisdomux_agents'), true);
    assert.equal(tables.has('wisdomux_tasks'), true);
    assert.equal(tables.has('wisdomux_events'), true);
    assert.equal(tables.has('wisdomux_proof_ledger'), true);
    assert.equal(
      db.prepare('SELECT COUNT(*) AS count FROM wisdomux_agents').get().count,
      0,
    );
    db.close();
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test('refuses to modify an existing database', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wisdomux-init-'));
  const databasePath = path.join(directory, 'existing.sqlite');
  try {
    const existing = new DatabaseSync(databasePath);
    existing.exec('CREATE TABLE sentinel (value TEXT NOT NULL)');
    existing.prepare('INSERT INTO sentinel (value) VALUES (?)').run('keep');
    existing.close();

    const result = spawnSync(process.execPath, [cli, '--db', databasePath], {
      encoding: 'utf8',
    });

    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /database already exists/);
    const db = new DatabaseSync(databasePath, { readOnly: true });
    assert.equal(db.prepare('SELECT value FROM sentinel').get().value, 'keep');
    assert.equal(
      db.prepare(
        "SELECT COUNT(*) AS count FROM sqlite_master WHERE name LIKE 'wisdomux_%'",
      ).get().count,
      0,
    );
    db.close();
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
