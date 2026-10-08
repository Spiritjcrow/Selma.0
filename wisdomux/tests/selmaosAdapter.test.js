'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const test = require('node:test');

const { SelmaOSAdapter } = require('../backend/adapters/selmaos');

async function runtimeFixture(handler) {
  const requests = [];
  const server = http.createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const body = chunks.length
      ? JSON.parse(Buffer.concat(chunks).toString('utf8'))
      : null;
    requests.push({
      method: request.method,
      url: request.url,
      headers: request.headers,
      body,
    });
    const result = await handler(request, body);
    response.writeHead(result.status, {
      'content-type': 'application/json; charset=utf-8',
    });
    response.end(JSON.stringify(result.body));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  return {
    adapter: new SelmaOSAdapter({
      baseUrl: `http://127.0.0.1:${address.port}`,
      timeoutMs: 1000,
    }),
    requests,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

test('reads status from the canonical SelmaOS loopback endpoint', async () => {
  const fixture = await runtimeFixture(async () => ({
    status: 200,
    body: { runtime: 'SELMA0_ANDROID_AGENT_V1' },
  }));
  try {
    const status = await fixture.adapter.status();

    assert.deepEqual(status, { runtime: 'SELMA0_ANDROID_AGENT_V1' });
    assert.equal(fixture.requests[0].method, 'GET');
    assert.equal(fixture.requests[0].url, '/api/selma0/status/v1');
  } finally {
    await fixture.close();
  }
});

test('executes through SelmaOS while preserving explicit approval state', async () => {
  const fixture = await runtimeFixture(async (_request, body) => ({
    status: 200,
    body: { ok: true, request_id: body.request_id, tool: body.tool },
  }));
  try {
    const result = await fixture.adapter.execute({
      taskId: 'task-1',
      tool: 'selma.status',
      arguments: {},
      approvalState: 'APPROVED',
    });

    assert.equal(result.ok, true);
    assert.deepEqual(fixture.requests[0].body, {
      tool: 'selma.status',
      arguments: {},
      approved: true,
      request_id: 'wisdomux:task-1',
    });
    assert.equal(
      fixture.requests[0].headers.origin,
      new URL(fixture.adapter.baseUrl).origin,
    );
  } finally {
    await fixture.close();
  }
});

test('does not translate pending approval into runtime authority', async () => {
  const fixture = await runtimeFixture(async (_request, body) => ({
    status: 409,
    body: {
      ok: false,
      requires_approval: true,
      approved_received: body.approved,
    },
  }));
  try {
    await assert.rejects(
      () =>
        fixture.adapter.execute({
          taskId: 'task-2',
          tool: 'selma.chat',
          arguments: { message: 'hello' },
          approvalState: 'PENDING',
        }),
      (error) => {
        assert.equal(error.status, 409);
        assert.equal(error.runtimeResult.approved_received, false);
        return true;
      },
    );
  } finally {
    await fixture.close();
  }
});

test('refuses non-loopback SelmaOS endpoints', () => {
  assert.throws(
    () => new SelmaOSAdapter({ baseUrl: 'https://selma.example.com' }),
    /loopback/,
  );
});
