/* Selma° HyperCore | 25-point offline evidence preflight. No network, no claim verification. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) api.mount(root.document, root);
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const STORE = 'selma.hypercore.proof.v0.2';
  const MAX_JSON_BYTES = 100000;
  const GATES = ['source', 'runner', 'sdk', 'lint', 'tests', 'apk', 'sha256', 'install'];
  // Samples are intentionally synthetic. Pattern matches only signal supplied fields, NEVER truth.
  const CHECKS = [
    ['01', 'source', 'Immutable commit ID', /\b[0-9a-f]{40}\b/i, '40-character commit SHA', 'a'.repeat(40)],
    ['02', 'source', 'Commit permalink', /https:\/\/github\.com\/[^\s/]+\/[^\s/]+\/commit\/[0-9a-f]{40}/i, 'GitHub commit permalink', 'https://github.com/x/y/commit/'+'a'.repeat(40)],
    ['03', 'source', 'Repository identity', /\bSpiritjcrow\/Selma\.0\b/i, 'Repository owner/name', 'Spiritjcrow/Selma.0'],
    ['04', 'source', 'Branch or ref label', /\b(?:branch|ref|head)\s*[:=]\s*[a-z0-9][a-z0-9._/-]{1,}/i, 'Named branch or ref', 'branch: feat/hypercore'],
    ['05', 'runner', 'Runner job identifier', /\b(?:build|job)[\s_-]*(?:id)?\s*[:=#]\s*[0-9a-f-]{12,}\b/i, 'Build/job ID', 'build_id: 6af6da0605c8b21ba24eec55'],
    ['06', 'runner', 'Runner detail URL', /https:\/\/codemagic\.io\/(?:app|builds)[^\s]*/i, 'Codemagic build link', 'https://codemagic.io/app/a/build/b'],
    ['07', 'runner', 'Workflow identity', /\bselma-android-debug\b/i, 'Workflow ID', 'selma-android-debug'],
    ['08', 'runner', 'Machine profile', /\b(?:mac_mini_m2|macOS\s+M2|runner\s*[:=]\s*\S+)/i, 'Runner model', 'mac_mini_m2'],
    ['09', 'sdk', 'Java runtime version', /\b(?:java|jdk)\s*(?:version|:)??\s*17\b/i, 'Java 17', 'Java 17'],
    ['10', 'sdk', 'Android SDK platform', /\b(?:android[-\s]35|API\s*35|platforms;android-35)\b/i, 'Platform 35', 'android-35'],
    ['11', 'sdk', 'Build-tools version', /\b(?:build-tools[;:/\s]+)?35\.0\.0\b/i, 'Build tools 35.0.0', 'build-tools;35.0.0'],
    ['12', 'sdk', 'Gradle version', /\bgradle\s*(?:version|:)??\s*8\.9\b/i, 'Gradle 8.9', 'Gradle 8.9'],
    ['13', 'lint', 'Lint execution command', /:app:lintDebug\b/i, 'Gradle lint task', ':app:lintDebug'],
    ['14', 'lint', 'Lint outcome statement', /\blint\s*(?:status|result|outcome)\s*[:=]\s*(?:pass|fail|success|error)/i, 'Explicit outcome, including failures', 'lint status: fail'],
    ['15', 'lint', 'Lint report reference', /\blint-results-debug(?:\.html|\.xml)\b/i, 'Report file reference', 'lint-results-debug.html'],
    ['16', 'tests', 'Unit-test execution command', /:app:testDebugUnitTest\b/i, 'Gradle unit-test task', ':app:testDebugUnitTest'],
    ['17', 'tests', 'Test-run summary', /\b(?:tests?\s*[:=]\s*\d+|\d+\s*tests?\b|\d+\s*\/\s*\d+\s*pass)/i, 'Count or pass ratio (not externally checked)', '12 tests'],
    ['18', 'tests', 'Test report reference', /\b(?:test-results|testDebugUnitTest|TEST-[\w.-]+\.xml)\b/i, 'Report or run ID', 'TEST-app.xml'],
    ['19', 'apk', 'APK artifact filename', /\b[\w.-]+\.apk\b/i, 'APK filename', 'app-debug.apk'],
    ['20', 'apk', 'Artifact download reference', /https:\/\/[^\s<>]+(?:\.apk\b|\/artifacts?\b)/i, 'HTTPS artifact link', 'https://example.test/artifacts/app-debug.apk'],
    ['21', 'apk', 'Artifact byte size', /\b(?:size|bytes)\s*[:=]\s*[1-9][0-9]*\b/i, 'Positive byte size', 'size: 10240'],
    ['22', 'sha256', '64-digit SHA-256 digest', /\b[0-9a-f]{64}\b/i, 'SHA-256 hexadecimal digest', 'b'.repeat(64)],
    ['23', 'sha256', 'Checksum command evidence', /\b(?:sha256sum|shasum\s+-a\s+256)\b/i, 'Hash command reference', 'sha256sum app-debug.apk'],
    ['24', 'install', 'Device and Android version', /\b(?:device|model)\s*[:=]\s*[^\n;]{3,}.{0,90}\b/i, 'Device model or platform', 'device: moto g play 2023, Android 13'],
    ['25', 'install', 'Install or smoke-test observation', /\b(?:adb\s+install|install\s*(?:result|status)|smoke[-\s]?test)\b/i, 'Observed install/smoke-test entry', 'install result: INSTALL_FAILED'],
  ].map(function (row) { return { id: row[0], gate: row[1], title: row[2], pattern: row[3], hint: row[4], sample: row[5] }; });

  function own(obj, key) { return Object.prototype.hasOwnProperty.call(obj, key); }
  function parseLedger(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw) || raw.schema !== 1 ||
        !raw.entries || typeof raw.entries !== 'object' || Array.isArray(raw.entries)) {
      throw new Error('Unsupported evidence-ledger schema');
    }
    const entries = Object.create(null);
    for (const gate of GATES) {
      if (!own(raw.entries, gate)) continue;
      const value = raw.entries[gate];
      if (!value || typeof value !== 'object' || Array.isArray(value) ||
          typeof value.evidence !== 'string' || value.evidence.length > 4000) {
        throw new Error('Invalid evidence structure for ' + gate);
      }
      entries[gate] = value.evidence;
    }
    return entries;
  }
  function evaluate(entries) {
    return CHECKS.map(function (check) {
      const value = own(entries, check.gate) ? entries[check.gate] : '';
      const status = !value || !value.trim() ? 'MISSING' : check.pattern.test(value) ? 'RECORDED_PATTERN' : 'REVIEW_FORMAT';
      return { id: check.id, gate: check.gate, title: check.title, hint: check.hint, status: status };
    });
  }
  function summarize(rows) {
    return {
      recorded: rows.filter(x => x.status === 'RECORDED_PATTERN').length,
      review: rows.filter(x => x.status === 'REVIEW_FORMAT').length,
      missing: rows.filter(x => x.status === 'MISSING').length,
      independently_verified: 0
    };
  }
  function mount(doc, win) {
    const byId = id => doc.getElementById(id);
    const cards = byId('checks');
    if (!cards) return;
    let sourceName = 'No local ledger found';
    let entries = Object.create(null);
    let latest = [];
    function message(text) { byId('notice').textContent = text; }
    function draw() {
      const rows = evaluate(entries);
      latest = rows;
      const sums = summarize(rows);
      byId('recorded-count').textContent = String(sums.recorded) + ' / 25';
      byId('review-count').textContent = String(sums.review);
      byId('missing-count').textContent = String(sums.missing);
      byId('source-name').textContent = sourceName;
      cards.replaceChildren();
      for (const row of rows) {
        const li = doc.createElement('li');
        li.className = 'check ' + row.status.toLowerCase();
        li.id = 'check-' + row.id;
        li.tabIndex = -1;
        const heading = doc.createElement('div'); heading.className = 'check-head';
        const title = doc.createElement('strong'); title.textContent = row.id + ' · ' + row.title;
        const state = doc.createElement('span'); state.className = 'state'; state.textContent = row.status.replace('_PATTERN', ' (UNVERIFIED)');
        const help = doc.createElement('p'); help.textContent = row.gate.toUpperCase() + ' · ' + row.hint;
        heading.append(title, state); li.append(heading, help); cards.appendChild(li);
      }
      const next = latest.find(x => x.status !== 'RECORDED_PATTERN');
      byId('next-label').textContent = next ? next.id + ' · ' + next.title : 'All 25 patterns recorded. Independent verification remains required.';
    }
    function loadLocal() {
      try {
        const input = win.localStorage.getItem(STORE);
        if (!input) { entries = Object.create(null); sourceName = 'No local ledger found'; }
        else {
          if (input.length > MAX_JSON_BYTES) throw new Error('Stored ledger is too large');
          entries = parseLedger(JSON.parse(input)); sourceName = 'Local browser ledger';
        }
        draw(); message('Preflight updated locally. Nothing was transmitted or verified.');
      } catch (error) { message('Local ledger unavailable: ' + error.message + '. Use JSON import.'); }
    }
    byId('refresh').addEventListener('click', loadLocal);
    byId('next').addEventListener('click', function () {
      const next = latest.find(x => x.status !== 'RECORDED_PATTERN') || latest[0];
      if (!next) return;
      const node = byId('check-' + next.id);
      node.focus(); if (typeof node.scrollIntoView === 'function') node.scrollIntoView({ block: 'center' });
      message('Next review: ' + next.id + '. This does not assign or execute a task.');
    });
    byId('import').addEventListener('change', async function (event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      try {
        if (file.size > MAX_JSON_BYTES) throw new Error('JSON file exceeds 100 KB');
        const parsed = parseLedger(JSON.parse(await file.text()));
        entries = parsed; sourceName = 'Imported file (in memory only)';
        draw(); message('Imported for local structural review only. Original ledger unchanged.');
      } catch (error) { message('Import rejected: ' + error.message); }
      finally { event.target.value = ''; }
    });
    byId('export').addEventListener('click', function () {
      const artifact = {
        schema: 1, type: 'selma-hypercore-preflight-summary',
        generated_at: new Date().toISOString(),
        source: sourceName, counters: summarize(latest),
        checks: latest, verdict: 'STRUCTURE_ONLY_UNVERIFIED',
        note: 'No raw evidence exported; no provenance or APK validity attested.'
      };
      const blob = new Blob([JSON.stringify(artifact, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = doc.createElement('a'); a.href = url; a.download = 'selma-hypercore-preflight.json';
      doc.body.appendChild(a); a.click(); a.remove();
      win.setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      message('Summary exported without evidence excerpts. No checks externally verified.');
    });
    draw(); loadLocal();
  }
  return { CHECKS, parseLedger, evaluate, summarize, mount };
});
