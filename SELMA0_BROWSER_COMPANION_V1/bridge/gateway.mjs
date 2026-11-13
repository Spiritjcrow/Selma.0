import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes, timingSafeEqual } from "node:crypto";
const DEFAULT_PORT = 18766;
const DEFAULT_UPSTREAM = "http://127.0.0.1:18765";

function compareToken(actual, expected) {
  if (!actual || typeof actual !== "string") return false;
  const a = Buffer.from(actual);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
export function createGateway({
  token = randomBytes(32).toString("hex"),
  upstream = DEFAULT_UPSTREAM,
  port = DEFAULT_PORT,
} = {}) {
  if (typeof token !== "string" || token.length < 16) throw Error("Token too short");
  const upstreamURL = new URL(upstream);
  if (upstreamURL.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(upstreamURL.hostname) ||
      upstreamURL.username || upstreamURL.password || upstreamURL.pathname !== "/") {
    throw Error("Upstream must be a loopback HTTP origin");
  }
  const server = http.createServer(async (req, res) => {
    const reply = (status, data) => {
      res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
      res.end(JSON.stringify(data));
    };
    if (req.headers.host !== `127.0.0.1:${server.address()?.port}`) {
      return reply(403, { ok: false, error: "invalid host" });
    }
    if (req.method !== "GET" || req.url !== "/v1/status") {
      return reply(404, { ok: false, error: "read-only status route only" });
    }
    if (!compareToken(req.headers["x-selma-bridge-token"], token)) {
      return reply(401, { ok: false, error: "token required" });
    }
    try {
      const response = await fetch(`${upstream}/api/selma0/status/v1`, {
        signal: AbortSignal.timeout(1500),
        redirect: "error",
        headers: { Accept: "application/json" }
      });
      if (!response.ok) return reply(502, { ok: false, error: "Selma backend unavailable" });
      const raw = await response.text();
      if (raw.length > 65536) return reply(502, { ok: false, error: "backend response too large" });
      const parsed = JSON.parse(raw);
      if (typeof parsed.name !== "string" || typeof parsed.runtime !== "string")
        return reply(502, { ok: false, error: "backend status invalid" });
      return reply(200, {
        ok: true, name: parsed.name, runtime: parsed.runtime,
        commandCoreAvailable: Boolean(parsed.command_core),
        mode: "read-only", transport: "local-loopback"
      });
    } catch {
      return reply(502, { ok: false, error: "Selma backend unavailable" });
    }
  });
  return { server, token, start: () => new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => { server.off("error", reject); resolve(server.address()); });
  }) };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const gateway = createGateway({ token: process.env.SELMA_BRIDGE_TOKEN || undefined, upstream: process.env.SELMA_BACKEND_URL || undefined });
  await gateway.start();
  console.log("Selma° local gateway: http://127.0.0.1:18766");
  console.log("Session token (enter in extension):", gateway.token);
  console.log("Read-only status endpoint. Stop with Ctrl+C.");
}
