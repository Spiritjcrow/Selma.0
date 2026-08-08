# Selma.0 RAG Memory V1

This milestone adds bounded, device-local retrieval over Selma's existing SQLite
conversation memory. SQLite FTS5 is used when the local Python build provides it;
a deterministic lexical scan of at most 5,000 recent events is the offline fallback.

The retrieved snippets are inserted before recent chat history and are explicitly
labeled as untrusted reference data. This prevents stored text from being treated as
instructions. Query size, result count, scan size, and per-snippet prompt length are
all bounded.

This is the lexical retrieval foundation, not semantic vector RAG. Embeddings,
`sqlite-vec`, document ingestion, retention controls, and user-facing memory editing
remain later milestones.
