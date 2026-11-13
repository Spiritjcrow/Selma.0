// CAPS-style real Chromium test: requires `npm install` and `npx playwright install chromium`.
import { chromium } from "playwright";
import assert from "node:assert/strict";
import http from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createGateway } from "../bridge/gateway.mjs";

const backend = http.createServer((_req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify({ name: "Selma.0", runtime: "E2E_TEST", memory_db: "MUST_NOT_LEAK" }));
});
let browser, gateway, profile;
try {
  await new Promise(resolve => backend.listen(0, "127.0.0.1", resolve));
  gateway = createGateway({ token: "e".repeat(32), upstream: `http://127.0.0.1:${backend.address().port}` });
  await gateway.start();
  profile = await mkdtemp(path.join(os.tmpdir(), "selma-caps-"));
  const extPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../dist");
  browser = await chromium.launchPersistentContext(profile, {
    channel: "chromium", headless: true,
    args: [`--disable-extensions-except=${extPath}`, `--load-extension=${extPath}`],
  });
  let worker = browser.serviceWorkers()[0];
  if (!worker) worker = await browser.waitForEvent("serviceworker");
  const extensionId = new URL(worker.url()).hostname;
  const page = await browser.newPage();
  await page.goto(`chrome-extension://${extensionId}/popup.html`);
  assert.match(await page.locator("#status").textContent(), /Disconnected/);
  await page.locator("#token").fill(gateway.token);
  await page.locator("#connect").click();
  await page.getByText("E2E_TEST").waitFor({ timeout: 8000 });
  assert.doesNotMatch(await page.locator("#status").textContent(), /MUST_NOT_LEAK/);
  await page.locator("#disconnect").click();
  assert.match(await page.locator("#status").textContent(), /Disconnected/);
  console.log("PASS: Chromium MV3 popup -> user-authorized gateway -> redacted Selma status");
} finally {
  if (browser) await browser.close();
  if (gateway) gateway.server.close();
  backend.close();
  if (profile) await rm(profile, { recursive: true, force: true });
}
