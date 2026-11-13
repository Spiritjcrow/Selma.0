import assert from "node:assert/strict";
import test from "node:test";
import http from "node:http";
import { createGateway } from "../bridge/gateway.mjs";

async function listen(server) {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  return server.address().port;
}
test("gateway requires secret, permits only status and redacts private backend fields", async t => {
  const upstream = http.createServer((req, res) => {
    assert.equal(req.url, "/api/selma0/status/v1");
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ name: "Selma.0", runtime: "SELMA0_ANDROID_AGENT_V1", memory_db: "/private/data", command_core: {secret: "redacted"} }));
  });
  const upstreamPort = await listen(upstream);
  t.after(() => upstream.close());
  const gateway = createGateway({ token: "a".repeat(32), upstream: `http://127.0.0.1:${upstreamPort}`, port: 0 });
  const address = await gateway.start();
  t.after(() => gateway.server.close());
  const url = `http://127.0.0.1:${address.port}`;
  assert.equal((await fetch(url + "/v1/status")).status, 401);
  assert.equal((await fetch(url + "/v1/status", { headers: { "X-Selma-Bridge-Token": "wrong" } })).status, 401);
  assert.equal((await fetch(url + "/api/selma0/tools/execute/v1", { headers: { "X-Selma-Bridge-Token": gateway.token } })).status, 404);
  assert.equal((await fetch(url + "/v1/status", { method: "POST", headers: { "X-Selma-Bridge-Token": gateway.token } })).status, 404);
  const response = await fetch(url + "/v1/status", { headers: { "X-Selma-Bridge-Token": gateway.token } });
  const value = await response.json();
  assert.deepEqual(value, { ok: true, name: "Selma.0", runtime: "SELMA0_ANDROID_AGENT_V1", commandCoreAvailable: true, mode: "read-only", transport: "local-loopback" });
  assert.doesNotMatch(JSON.stringify(value), /private|secret/);
});
test("gateway fails closed if upstream is unreachable", async t => {
  const gateway = createGateway({ token: "a".repeat(32), upstream: "http://127.0.0.1:1", port: 0 });
  const address = await gateway.start();
  t.after(() => gateway.server.close());
  const response = await fetch(`http://127.0.0.1:${address.port}/v1/status`, { headers: { "X-Selma-Bridge-Token": gateway.token } });
  assert.equal(response.status, 502);
  assert.equal((await response.json()).ok, false);
});
test("gateway rejects network-facing upstreams", () => {
  assert.throws(() => createGateway({ upstream: "https://example.com/" }), /loopback/);
});
