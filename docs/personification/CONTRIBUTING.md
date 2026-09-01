# Safe personification registry

The registry describes how an original or authorized character behaves across renderers. It is not a biography database, biometric store, training corpus, or permission system. Personifications never authorize tools or external effects.

## Add a record

1. Copy the deterministic synthetic fixture and assign a stable `personification:` ID plus semantic `record_version`.
2. Keep factual biography, authored character design, inferred preferences, and generated synthetic assets in their separate arrays. Every item must reference a provenance entry; every inference must include confidence.
3. Record the asset origin, SPDX license expression, attribution and commercial-use status. Unknown commercial rights block release.
4. For any real subject, store only a reference to documented authorization—not private evidence—and set both likeness and voice status to `documented-authorization`. Never approximate a living person's protected likeness or voice.
5. Map the seven renderer-neutral states and normalized expression parameters. Renderers may ignore unsupported parameters but must use the declared fallback.
6. Run `python3 -m unittest tests.test_personification_registry` and `python3 tools/validate_personifications.py <record> <mapping>`.

## Prohibited data

Do not add secrets, credentials, private conversations, medical records, biometric templates, scraped personal data, or unreviewed training material. Prefer authored, consented, licensed, public-domain, or transparently synthetic assets.

## Compatibility and migration

- Patch versions clarify metadata without changing behavior.
- Minor versions may add optional fields and mappings. Old renderers must apply fallbacks.
- Major versions may change required fields or meaning and require a new schema and explicit migration tool.
- Migrations are pure, deterministic transformations. Preserve the old record digest, source IDs and license facts; never upgrade `unknown` rights to `allowed` automatically.

## Quality gates

Release requires schema validity, complete provenance references, complete renderer state coverage, accessibility review, deterministic serialization, license review, and authorization review where a real subject is involved. Runtime metrics later include state-transition correctness, interruption latency, caption coverage, localization coverage, animation frame stability and user-controlled reduced-motion behavior.

## Standards references

- JSON Schema Draft 2020-12: https://json-schema.org/draft/2020-12/json-schema-core
- Semantic Versioning 2.0.0: https://semver.org/spec/v2.0.0.html
- SPDX license expressions: https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions/
- IETF BCP 47 language tags (RFC 5646): https://www.rfc-editor.org/rfc/rfc5646
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
