# Selma Repo Fabric contract v1

This slice implements issue #33's first provider-neutral repository boundary.

It does not authenticate to a provider, open a network connection, execute a build, deploy software, or grant repository authority. It defines exact provider/repository/ref/vault/path scope and a fail-closed null adapter.

## Security properties

- External repository actions still require an approved Gate 1 `InvocationContext`.
- The default remote-provider capability is `NETWORK`; the adapter cannot downgrade the Gate 1 risk floor.
- Missing authenticated identity fails closed.
- Repository and ref scope are exact.
- Optional vault path prefixes prevent an adapter from wandering into unrelated repository sections.
- Requested operations must be explicitly allowed by the scope.
- Cancellation is checked before provider scope work.
- The null adapter can never report success.
- No credential, API token, provider endpoint, or account secret is stored.

## Intended provider mappings

The same contract can back:
- GitHub connector/provider adapters;
- GitLab OpenAI/MCP adapters;
- Codeberg/Forgejo adapters;
- local filesystem/terminal bridges using a storage/process capability rather than network.

Real provider implementations remain separate and must preserve the existing Selma permission, replay-protection, and audit path.
