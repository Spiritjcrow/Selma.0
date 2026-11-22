# SelmaOS Command Center (Webflow-compatible)

Static responsive HTML/CSS/JavaScript dashboard. Open index.html directly or host the folder on any static host. Webflow integration may use a custom-code embed or an independently hosted page; publishing has not been performed.

## Features
- Read-only public GitHub Actions run metadata (no GitHub token required)
- Manual refresh and optional five-minute refresh while the page remains open
- Black / White / UltraViolet roles explicitly marked *not connected*
- Browser-local audit log and JSON export
- Responsive mobile layout; safe text rendering of API fields

## Boundaries
- No live agent control, no secrets, no APK validation, no 24/7 server-side scheduler.
- GitHub API availability and browser CORS/network access determine live refresh.
- A successful workflow conclusion alone does not prove an APK was installed or tested.
- Local audit is editable by the browser user and is not tamper-evident court evidence.

## Verification
Run `node --check app.js` and inspect the page in a browser. Browser and deployment verification remain pending.
