# SelmaOS offline browser recovery

This is a **new reconstruction**. The other cloud environment reported `409 Conflict: environment_offline` for `/workspace/sites/selmaos/selmaos.html`. Screenshots cannot recover that workspace's original bytes, and we do not claim to have recovered or copied them.

## Use

Open `sites/selmaos/selmaos.html` as a local file in a modern browser, or from the repo root run:

```sh
python3 -m http.server 8765 --directory sites/selmaos
```

Then open `http://127.0.0.1:8765/selmaos.html` on that same machine. To use offline on Android, copy the single HTML file to Android storage and open with a browser that supports local HTML. Browser file permissions and storage persistence vary.

## Implemented

- Responsive desktop, app drawer, simulated boot screen, animated **abstract** portrait.
- Local notes autosave and reminders (check/delete).
- In-tab 25-minute focus timer and arithmetic calculator (no `eval`).
- Explicitly selected local file previews (text and image, <= 256 KB, no upload).
- Validated JSON data backup import/export.
- Secondary browser tab request; popup policies may block it.

## Not implemented

Not a Linux VM or native Android OS, not a remote workspace recovery, not a lifelike 3D rig, no offline/online conversational model, no overlay, no voice assistant, no cloud sync. Data is site/browser-local and can be cleared. Export backups frequently and do not store secrets in notes.

No hardcoded SSID, router, carrier, external endpoint, provider, or API credential.

## Validation

```sh
python3 -m unittest tests.test_selmaos_recovery_html -v
```

These are static smoke contracts only. Real browser/device and live deployment verification are pending.
