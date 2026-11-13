const statusUrl = "http://127.0.0.1:18766/v1/status";
type StatusRequest = { kind: "SELMA_READ_ONLY_STATUS" };
chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return false;
  if (!message || (message as StatusRequest).kind !== "SELMA_READ_ONLY_STATUS") return false;
  (async () => {
    const values = await chrome.storage.session.get(["selmaGatewayToken"]);
    const token = values.selmaGatewayToken;
    if (typeof token !== "string" || token.length < 16) {
      return { ok: false, error: "Not connected: user approval required" };
    }
    const controller = new AbortController();
    const deadline = setTimeout(() => controller.abort(), 2000);
    try {
      const response = await fetch(statusUrl, {
        method: "GET",
        headers: { "X-Selma-Bridge-Token": token },
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) return { ok: false, error: `Local gateway status ${response.status}` };
      return await response.json();
    } catch {
      return { ok: false, error: "Local gateway unreachable; no fallback" };
    } finally { clearTimeout(deadline); }
  })().then(sendResponse, () => sendResponse({ ok: false, error: "Bridge error" }));
  return true;
});
