const bridgePermission = "http://127.0.0.1:18766/*";
const statusEl = document.querySelector<HTMLElement>("#status")!;
const tokenEl = document.querySelector<HTMLInputElement>("#token")!;
const connectEl = document.querySelector<HTMLButtonElement>("#connect")!;
const refreshEl = document.querySelector<HTMLButtonElement>("#refresh")!;
const disconnectEl = document.querySelector<HTMLButtonElement>("#disconnect")!;

function report(value: unknown): void {
  statusEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
async function refresh(): Promise<void> {
  report("Checking local gateway…");
  try {
    report(await chrome.runtime.sendMessage({ kind: "SELMA_READ_ONLY_STATUS" }));
  } catch {
    report("Gateway unavailable. No remote fallback.");
  }
}
connectEl.addEventListener("click", async () => {
  const token = tokenEl.value.trim();
  if (token.length < 16 || token.length > 256) {
    report("Enter the session token printed by the gateway.");
    return;
  }
  try {
    const granted = await chrome.permissions.request({ origins: [bridgePermission] });
    if (!granted) { report("Local host permission declined."); return; }
    await chrome.storage.session.set({ selmaGatewayToken: token });
    tokenEl.value = "";
    await refresh();
  } catch { report("Could not connect. Check extension permissions."); }
});
refreshEl.addEventListener("click", () => { void refresh(); });
disconnectEl.addEventListener("click", async () => {
  await chrome.storage.session.remove(["selmaGatewayToken"]);
  await chrome.permissions.remove({ origins: [bridgePermission] });
  report("Disconnected");
});
