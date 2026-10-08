'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { ProofLedger } = require('../backend/proofLedger');

function migration(name) {
  return fs.readFileSync(
    path.join(__dirname, '..', 'db', 'migrations', name),
    'utf8',
  );
}

function fixture() {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration('001_coordination_core.sql'));
  db.exec(migration('002_proof_ledger.sql'));
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, ?, ?, 'ONLINE', ?)`,
  ).run(
    'qa-1',
    'QA One',
    'QA',
    JSON.stringify({ grants: ['proof.record'] }),
    '2026-10-08T16:00:00.000Z',
  );
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status, created_at)
     VALUES (?, ?, ?, ?, 'ONLINE', ?)`,
  ).run(
    'observer',
    'Observer',
    'Research',
    JSON.stringify({ grants: ['observe'] }),
    '2026-10-08T16:00:00.000Z',
  );
  let sequence = 0;
  const ledger = new ProofLedger(db, {
    now: () => `2026-10-08T16:0${sequence++}:00.000Z`,
    newId: () => `proof-${sequence}`,
  });
  return { db, ledger };
}

test('appends verifiable proof entries as a hash chain', () => {
  const { ledger } = fixture();
  const first = ledger.record({
    projectId: 'wisdomux',
    actorAgent: 'qa-1',
    claim: 'migration tests passed',
    truthState: 'REAL',
    evidenceRefs: ['test://migration/4-pass'],
  });
  const second = ledger.record({
    projectId: 'wisdomux',
    actorAgent: 'qa-1',
    claim: 'queue tests passed',
    truthState: 'REAL',
    evidenceRefs: ['test://queue/4-pass'],
  });

  assert.equal(first.previous_hash, null);
  assert.equal(second.previous_hash, first.entry_hash);
  assert.deepEqual(ledger.verify(), {
    ok: true,
    entries: 2,
    head: second.entry_hash,
  });
});

test('rejects proof writes from an unauthorized agent', () => {
  const { ledger } = fixture();

  assert.throws(
    () =>
      ledger.record({
        projectId: 'wisdomux',
        actorAgent: 'observer',
        claim: 'unsupported claim',
        truthState: 'UNVERIFIED',
        evidenceRefs: [],
      }),
    /missing capability: proof.record/,
  );
});

test('ledger rows are append-only', () => {
  const { db, ledger } = fixture();
  ledger.record({
    projectId: 'wisdomux',
    actorAgent: 'qa-1',
    claim: 'verified claim',
    truthState: 'REAL',
    evidenceRefs: [],
  });

  assert.throws(
    () =>
      db.prepare(
        "UPDATE wisdomux_proof_ledger SET claim = 'altered' WHERE sequence = 1",
      ).run(),
    /append-only/,
  );
  assert.throws(
    () =>
      db.prepare(
        'DELETE FROM wisdomux_proof_ledger WHERE sequence = 1',
      ).run(),
    /append-only/,
  );
});

test('verification detects an invalid injected chain entry', () => {
  const { db, ledger } = fixture();
  const first = ledger.record({
    projectId: 'wisdomux',
    actorAgent: 'qa-1',
    claim: 'verified claim',
    truthState: 'REAL',
    evidenceRefs: [],
  });
  db.prepare(
    `INSERT INTO wisdomux_proof_ledger
      (entry_id, project_id, task_id, actor_agent, claim, truth_state,
       evidence_json, previous_hash, entry_hash, created_at)
     VALUES (?, ?, NULL, ?, ?, ?, '[]', ?, ?, ?)`,
  ).run(
    'forged',
    'wisdomux',
    'qa-1',
    'forged claim',
    'REAL',
    first.entry_hash,
    '0'.repeat(64),
    '2026-10-08T16:09:00.000Z',
  );

  const verification = ledger.verify();
  assert.equal(verification.ok, false);
  assert.equal(verification.sequence, 2);
  assert.equal(verification.error, 'entry hash mismatch');
});
