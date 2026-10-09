'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { DatabaseSync } = require('node:sqlite');

const { AgentRegistry } = require('../backend/agentRegistry');

const migration = fs.readFileSync(
  path.join(__dirname, '..', 'db', 'migrations', '001_coordination_core.sql'),
  'utf8',
);

function fixture(options = {}) {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec(migration);
  db.prepare(
    `INSERT INTO wisdomux_agents
      (agent_id, display_name, role, capability_json, status,
       last_seen_at, created_at)
     VALUES ('coordinator-1', 'Coordinator One', 'Coordinator', ?,
             'ONLINE', ?, ?)`,
  ).run(
    JSON.stringify({
      grants: options.coordinatorGrants || ['agent.register', 'agent.monitor'],
    }),
    '2026-10-09T01:00:00.000Z',
    '2026-10-09T01:00:00.000Z',
  );
  let id = 0;
  const registry = new AgentRegistry(db, {
    now: () => '2026-10-09T01:01:00.000Z',
    newId: options.newId || (() => `registry-${++id}`),
  });
  return { db, registry };
}

function register(registry, overrides = {}) {
  return registry.register({
    projectId: 'wisdomux',
    requestedBy: 'coordinator-1',
    agentId: 'builder-1',
    displayName: 'Builder One',
    role: 'Backend',
    grants: ['task.execute', 'task.execute', 'task.verify'],
    ...overrides,
  });
}

test('registers an online agent with normalized grants and audit evidence', () => {
  const { db, registry } = fixture();

  const agent = register(registry);

  assert.equal(agent.status, 'ONLINE');
  assert.equal(agent.last_seen_at, '2026-10-09T01:01:00.000Z');
  assert.deepEqual(JSON.parse(agent.capability_json), {
    grants: ['task.execute', 'task.verify'],
  });
  const event = db.prepare(
    "SELECT * FROM wisdomux_events WHERE event_type = 'AGENT_REGISTERED'",
  ).get();
  assert.equal(event.sender_agent, 'coordinator-1');
  assert.deepEqual(JSON.parse(event.payload_json), {
    agent_id: 'builder-1',
    display_name: 'Builder One',
    role: 'Backend',
    grants: ['task.execute', 'task.verify'],
  });
});

test('requires registrar authority', () => {
  const { registry } = fixture({ coordinatorGrants: ['agent.monitor'] });

  assert.throws(() => register(registry), /missing capability: agent.register/);
});

test('rolls back registration when audit evidence cannot be recorded', () => {
  const { db, registry } = fixture({ newId: () => 'collision' });
  db.prepare(
    `INSERT INTO wisdomux_events
      (event_id, project_id, event_type, truth_state, created_at)
     VALUES ('collision', 'wisdomux', 'EXISTING', 'REAL', ?)`,
  ).run('2026-10-09T01:00:30.000Z');

  assert.throws(() => register(registry), /UNIQUE constraint failed/);
  assert.equal(
    db.prepare(
      "SELECT COUNT(*) AS count FROM wisdomux_agents WHERE agent_id = 'builder-1'",
    ).get().count,
    0,
  );
});

test('rejects malformed capability grants before registration', () => {
  const { registry } = fixture();

  assert.throws(
    () => register(registry, { grants: ['task.execute', ''] }),
    /grants must contain non-empty strings/,
  );
});

test('accepts an identity-matched heartbeat and updates liveness', () => {
  const { db, registry } = fixture();
  register(registry);

  const agent = registry.heartbeat({
    agentId: 'builder-1',
    authenticatedAgentId: 'builder-1',
    status: 'BUSY',
  });

  assert.equal(agent.status, 'BUSY');
  assert.equal(agent.last_seen_at, '2026-10-09T01:01:00.000Z');
  assert.equal(
    db.prepare(
      "SELECT COUNT(*) AS count FROM wisdomux_events WHERE event_type = 'AGENT_HEARTBEAT'",
    ).get().count,
    0,
  );
});

test('rejects a heartbeat reported as another agent', () => {
  const { registry } = fixture();
  register(registry);

  assert.throws(
    () => registry.heartbeat({
      agentId: 'builder-1',
      authenticatedAgentId: 'coordinator-1',
      status: 'ONLINE',
    }),
    /heartbeat identity mismatch/,
  );
});

test('does not let a revoked agent reactivate itself', () => {
  const { db, registry } = fixture();
  register(registry);
  db.prepare(
    "UPDATE wisdomux_agents SET status = 'REVOKED' WHERE agent_id = 'builder-1'",
  ).run();

  assert.throws(
    () => registry.heartbeat({
      agentId: 'builder-1',
      authenticatedAgentId: 'builder-1',
      status: 'ONLINE',
    }),
    /revoked agent cannot send heartbeat/,
  );
});

test('expires only stale active agents and records the cutoff', () => {
  const { db, registry } = fixture();
  register(registry);
  register(registry, {
    agentId: 'builder-2',
    displayName: 'Builder Two',
  });
  db.prepare(
    "UPDATE wisdomux_agents SET last_seen_at = ? WHERE agent_id = 'builder-1'",
  ).run('2026-10-09T00:30:00.000Z');

  const expired = registry.expireStale({
    projectId: 'wisdomux',
    requestedBy: 'coordinator-1',
    cutoff: '2026-10-09T00:45:00.000Z',
  });

  assert.deepEqual(expired, ['builder-1']);
  assert.equal(
    db.prepare("SELECT status FROM wisdomux_agents WHERE agent_id = 'builder-1'").get().status,
    'OFFLINE',
  );
  assert.equal(
    db.prepare("SELECT status FROM wisdomux_agents WHERE agent_id = 'builder-2'").get().status,
    'ONLINE',
  );
  const event = db.prepare(
    "SELECT * FROM wisdomux_events WHERE event_type = 'AGENT_MARKED_STALE'",
  ).get();
  assert.deepEqual(JSON.parse(event.payload_json), {
    agent_id: 'builder-1',
    previous_status: 'ONLINE',
    cutoff: '2026-10-09T00:45:00.000Z',
    last_seen_at: '2026-10-09T00:30:00.000Z',
  });
});

test('requires monitoring authority to expire stale agents', () => {
  const { registry } = fixture({ coordinatorGrants: ['agent.register'] });

  assert.throws(
    () => registry.expireStale({
      projectId: 'wisdomux',
      requestedBy: 'coordinator-1',
      cutoff: '2026-10-09T00:45:00.000Z',
    }),
    /missing capability: agent.monitor/,
  );
});
