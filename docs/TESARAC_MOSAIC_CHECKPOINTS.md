# Tesarac modular mosaic diagnostic checkpoints, v0.1

Tracks [issue #112](https://github.com/Spiritjcrow/Selma.0/issues/112) and durable queue [#88](https://github.com/Spiritjcrow/Selma.0/issues/88). This is a **local diagnostic/evidence integrity tool**, not a certified notary, a data authenticity guarantee, an independent witness, or a deployed 24/7 service.

## Design

Mosaic JSON plan → schema/dependency validation → ordered unit runner → JSONL hash chain → summary checkpoint → independent verification.

- **Unit:** a typed, bounded action: allowlisted note, logcat, interfaces, partition. No arbitrary shell commands, root access, packet sniffing or network egress.
- **Modulation:** JSON depends_on and required enforce ordered execution. A dependent unit only runs if each predecessor is PASS. NOT_RUN never implies a successful test.
- **String mosaic:** note accepts an array of UTF-8 segments and a separator. Assembled strings are recorded verbatim as NON-EXECUTABLE notes. Use required=false for informational notes.
- **Session hash chain:** each JSONL line includes session UUID, 0-based sequence, UTC, event kind, prior digest, SHA-256 of canonical event content. Append uses POSIX flock and fsync. Ledger capped at 16 MiB, record at 512 KiB. Android Termux/Linux/macOS supported; Windows fails closed until an equivalent lock exists.
- **Probes:** logcat -d -t 250; ifconfig -a with fallback ip -br addr. Read-only local diagnostics with 8-second timeout; records only output digest, byte count, line count and monotonic elapsed milliseconds. Raw output, addresses and logs are neither printed nor persisted.
- **Partition:** hash byte ranges of an existing local file, 1 KiB to 1 MiB chunk sizes and up to 1024 chunks. This is NOT live packet capture or PCAP decoding. Source files must be stable during inspection.
- **Verdicts:** required diagnostic units PASS only on actual execution with zero return code. Missing tools and failed preconditions BLOCKED; note-only checkpoint NOT_RUN; mosaic PASS only when ALL required units PASS.

## Android / Termux copy-paste commands

Run in the repository branch checkout after installing Python 3:

~~~sh
python tools/tesarac.py init --ledger "$HOME/tesarac-session.jsonl"
python tools/tesarac.py note --ledger "$HOME/tesarac-session.jsonl" --text 'Initial checkpoint' --artifact 'https://github.com/Spiritjcrow/Selma.0/issues/112'
python tools/tesarac.py capture --ledger "$HOME/tesarac-session.jsonl" --kind logcat
python tools/tesarac.py capture --ledger "$HOME/tesarac-session.jsonl" --kind interfaces
python tools/tesarac.py verify --ledger "$HOME/tesarac-session.jsonl"
~~~

If logcat or ifconfig are absent or Android permissions restrict access, the result is BLOCKED and recorded as such. For an existing file you own, partition with:

~~~sh
python tools/tesarac.py partition --ledger "$HOME/tesarac-session.jsonl" --file "$HOME/owned-capture.pcap" --chunk-bytes 65536
~~~

Replace the sample path with a real file. Do not record API keys, credentials, device identifiers or sensitive personal information in free-form text notes.

## Mosaic plan example

Save the following content as mosaic-plan.json (or use the separately committed docs/mosaic-plan-example.json):

~~~json
{
  "version": 1,
  "units": [
    {"id": "context", "kind": "note", "segments": ["Selma", "Tesarac", "session"], "separator": " / ", "required": false},
    {"id": "interfaces", "kind": "interfaces", "required": true},
    {"id": "logcat", "kind": "logcat", "depends_on": ["interfaces"], "required": true}
  ]
}
~~~

Then execute:

~~~sh
python tools/tesarac.py mosaic --ledger "$HOME/tesarac-session.jsonl" --plan docs/mosaic-plan-example.json
~~~

## External anchors and limits

Every tool result has a head_sha256 digest; verification recomputes all sequence numbers, links, canonical hashes and event schema. To detect deletion of trailing, individually valid lines, preserve the last head_sha256 **and** records count in a separate trusted location. Example verification, using values actually recorded elsewhere:

~~~sh
python tools/tesarac.py verify --ledger "$HOME/tesarac-session.jsonl" --expected-sha256 SAVED_SHA256 --expected-count SAVED_COUNT
~~~

These named values are documentation placeholders, not test evidence. A SHA-256 chain cannot authenticate the observer or guarantee logs were true; without an independent outside anchor an attacker with write access can rewrite the entire chain. UTC comes from the local device clock, not an externally trusted time authority. A saved output digest does not preserve the output itself. For court-facing provenance, retain the originals in access-controlled storage and obtain independent review.

## Tests and status

~~~sh
python -m unittest discover -s tests -p 'test_tesarac.py' -v
~~~

Local isolated Linux reference execution: 16/16 tests PASS. 100 event appended/check-verified/fsync operations: mean 1.413 ms, p95 2.218 ms, max 6.909 ms in one local run, ledger size 34,240 bytes after 101 records. Hash partition of 1 MiB into 16 parts at 64 KiB averaged 1.545 ms over 10 local passes. These are reference measurements, **not promised Android device latencies**.

The repo's GitHub Actions job startup failure (#26) remains separate: no hosted CI PASS is claimed, and no Android handset tests or independent White/UltraViolet review have yet been observed. No service, daemon, merge, signing, external publishing or release occurs here.
