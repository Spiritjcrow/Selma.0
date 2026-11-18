# Selma EarthWatch: offline evidence review (pilot)

**Status:** Portable read-only demonstration. Not a live air monitor, official-alert client, emergency-warning service or verified environmental measurement system. Related issue: #58.

## Use

Run from the repository root with Python 3.11+:

~~~bash
python3 -m unittest tests.test_earthwatch -v
python3 -m tools.earthwatch_review path/to/snapshot.json
~~~

Input example (illustrative only, **not a real alert**):

~~~json
{"schema_version":1,"observations":[{"source_record_id":"example-1","source_url":"https://example.org/report","category":"air_quality","place":"Example City","observed_at":"2026-10-13T15:00:00Z","reported_severity":"info","summary":"Example-only observation; not an air-quality measurement"}]}
~~~

All imports are labelled **unverified**, including HTTPS links to seemingly official sources. The code never fetches URLs or authenticates their publishers. Reported severity is copied for human review, never translated into a safety alarm. Duplicate source IDs with conflicting content fail closed. Fast-changing categories become stale after 72 hours; structural categories after one year. These are display-review windows, **not scientific safety thresholds**. Any future-dated report more than five minutes ahead is flagged.

Reviewing a local JSON file requires no GPS, root access, AR hardware, Android overlays, network connectivity, external credentials or system services. It sends nothing. File contents should not include personal identifiers, private addresses, people tracking or credentials.

## Next gates

- Independent review of provenance and licensing for each proposed public dataset.
- Permission-gated and revocable official feed adapters, with source authentication, regional coverage, caching/expiration and explicit offline/unknown states.
- Source-specific quantitative units and validated health guidance before interpreting pollution, heat or water measurements.
- User-controlled non-AR UI, accessible on low-spec Android, plus community partners to translate observations into improvements.
- No automatic public alerts or physical actions without source verification, explicit permission, safety review and an audited notification pathway.

Related system concerns: #17 (core tracker), #39 (offline connectivity), #26 (repository Actions startup failure). This module does not close those issues.
