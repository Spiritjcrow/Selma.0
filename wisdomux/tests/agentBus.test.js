'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const { AgentBus } = require('../backend/agentBus');

class RecordingSocket {
  constructor() {
    this.sent = [];
    this.closed = null;
  }

  send(value) {
    this.sent.push(JSON.parse(value));
  }

  close(code, reason) {
    this.closed = { code, reason };
  }
}

function message(overrides = {}) {
  return {
    protocol_version: 'wisdomux.agent-message.v1',
    message_id: 'message-1',
    project_id: 'wisdomux',
    task_id: 'task-1',
    sender_agent: 'selma',
    recipient_agent: 'kai',
    intent: 'HANDOFF',
    truth_state: 'REAL',
    created_at: '2026-10-08T08:00:00.000Z',
    approval_state: 'NOT_REQUIRED',
    ...overrides,
  };
}

test('routes a direct message only to its registered recipient', () => {
  const bus = new AgentBus({ now: () => '2026-10-08T08:01:00.000Z' });
  const selma = new RecordingSocket();
  const kai = new RecordingSocket();
  const solBlue = new RecordingSocket();
  bus.attach(selma, { agentId: 'selma', projectIds: ['wisdomux'] });
  bus.attach(kai, { agentId: 'kai', projectIds: ['wisdomux'] });
  bus.attach(solBlue, { agentId: 'sol-blue', projectIds: ['wisdomux'] });

  const result = bus.receive(selma, JSON.stringify(message()));

  assert.deepEqual(result, { delivered: 1, duplicate: false });
  assert.equal(kai.sent[0].message_id, 'message-1');
  assert.equal(solBlue.sent.length, 0);
});

test('rejects a message whose sender does not own the connection', () => {
  const bus = new AgentBus({ now: () => '2026-10-08T08:01:00.000Z' });
  const attacker = new RecordingSocket();
  bus.attach(attacker, { agentId: 'unknown', projectIds: ['wisdomux'] });

  assert.throws(
    () => bus.receive(attacker, JSON.stringify(message())),
    /sender does not own connection/,
  );
  assert.deepEqual(attacker.closed, {
    code: 1008,
    reason: 'sender does not own connection',
  });
});

test('keeps project broadcasts inside the authorized project', () => {
  const bus = new AgentBus({ now: () => '2026-10-08T08:01:00.000Z' });
  const selma = new RecordingSocket();
  const kai = new RecordingSocket();
  const outside = new RecordingSocket();
  bus.attach(selma, { agentId: 'selma', projectIds: ['wisdomux'] });
  bus.attach(kai, { agentId: 'kai', projectIds: ['wisdomux'] });
  bus.attach(outside, { agentId: 'outside', projectIds: ['other-project'] });

  bus.receive(
    selma,
    JSON.stringify(
      message({
        recipient_agent: null,
        broadcast_scope: 'PROJECT',
      }),
    ),
  );

  assert.equal(kai.sent.length, 1);
  assert.equal(outside.sent.length, 0);
});

test('rejects expired and replayed messages', () => {
  const bus = new AgentBus({ now: () => '2026-10-08T08:01:00.000Z' });
  const selma = new RecordingSocket();
  const kai = new RecordingSocket();
  bus.attach(selma, { agentId: 'selma', projectIds: ['wisdomux'] });
  bus.attach(kai, { agentId: 'kai', projectIds: ['wisdomux'] });

  assert.throws(
    () =>
      bus.receive(
        selma,
        JSON.stringify(
          message({
            message_id: 'expired',
            expires_at: '2026-10-08T08:00:59.000Z',
          }),
        ),
      ),
    /message has expired/,
  );

  bus.receive(selma, JSON.stringify(message()));
  const replay = bus.receive(selma, JSON.stringify(message()));
  assert.deepEqual(replay, { delivered: 0, duplicate: true });
  assert.equal(kai.sent.length, 1);
});
