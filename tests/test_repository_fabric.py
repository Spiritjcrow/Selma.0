from __future__ import annotations

import unittest

from adapters.repository_null import NullRepositoryProviderAdapter
from core.protocols import (
    CancellationToken,
    Capability,
    InvocationContext,
    ResultStatus,
)
from core.repository import RepositoryOperation, RepositoryRequest, RepositoryScope


class RepositoryFabricContractTests(unittest.TestCase):
    def scope(
        self,
        *,
        identity: str | None = "authenticated-test-user",
        operations=frozenset({RepositoryOperation.READ}),
        prefixes=("selma/core",),
    ) -> RepositoryScope:
        return RepositoryScope(
            provider="test-provider",
            repository="owner/repo",
            ref="main",
            vault_id="core",
            identity=identity,
            capability=Capability.NETWORK,
            allowed_operations=operations,
            path_prefixes=prefixes,
        )

    def request(
        self,
        operation: RepositoryOperation = RepositoryOperation.READ,
        *,
        repository: str = "owner/repo",
        ref: str = "main",
        path: str = "selma/core/protocols.py",
    ) -> RepositoryRequest:
        return RepositoryRequest(operation, repository, ref, path)

    def approved(
        self,
        operation: RepositoryOperation = RepositoryOperation.READ,
        *,
        cancellation: CancellationToken | None = None,
    ) -> InvocationContext:
        return InvocationContext.approved_call(
            "repo-contract",
            capability=Capability.NETWORK,
            operation=f"repo.{operation.value}",
            cancellation=cancellation,
        )

    def test_valid_scoped_request_remains_unavailable_not_success(self) -> None:
        adapter = NullRepositoryProviderAdapter(self.scope())
        result = adapter.invoke(self.request(), {}, self.approved())
        self.assertEqual(ResultStatus.UNAVAILABLE, result.status)
        self.assertFalse(result.ok)
        self.assertEqual("core", result.data["vault_id"])

    def test_missing_identity_fails_closed(self) -> None:
        adapter = NullRepositoryProviderAdapter(self.scope(identity=None))
        result = adapter.invoke(self.request(), {}, self.approved())
        self.assertEqual(ResultStatus.DENIED, result.status)

    def test_wrong_repository_and_ref_fail_closed(self) -> None:
        adapter = NullRepositoryProviderAdapter(self.scope())
        repo = adapter.invoke(self.request(repository="other/repo"), {}, self.approved())
        ref = adapter.invoke(self.request(ref="feature"), {}, self.approved())
        self.assertEqual(ResultStatus.DENIED, repo.status)
        self.assertEqual(ResultStatus.DENIED, ref.status)

    def test_write_requires_scope_and_matching_control_plane_approval(self) -> None:
        adapter = NullRepositoryProviderAdapter(self.scope())
        write_request = self.request(RepositoryOperation.WRITE)
        denied_by_context = adapter.invoke(write_request, {}, self.approved())
        denied_by_scope = adapter.invoke(
            write_request,
            {},
            self.approved(RepositoryOperation.WRITE),
        )
        self.assertEqual(ResultStatus.DENIED, denied_by_context.status)
        self.assertEqual(ResultStatus.DENIED, denied_by_scope.status)

    def test_cancellation_wins_before_provider_scope_checks(self) -> None:
        token = CancellationToken()
        token.cancel()
        adapter = NullRepositoryProviderAdapter(self.scope(identity=None))
        result = adapter.invoke(
            self.request(),
            {},
            self.approved(cancellation=token),
        )
        self.assertEqual(ResultStatus.CANCELLED, result.status)

    def test_vault_path_prefix_is_enforced(self) -> None:
        adapter = NullRepositoryProviderAdapter(self.scope())
        outside = adapter.invoke(
            self.request(path="selma/avatar/renderer.py"),
            {},
            self.approved(),
        )
        self.assertEqual(ResultStatus.DENIED, outside.status)

    def test_path_traversal_is_rejected_at_request_boundary(self) -> None:
        with self.assertRaises(ValueError):
            self.request(path="../secrets.txt")

    def test_shutdown_is_visible(self) -> None:
        adapter = NullRepositoryProviderAdapter(self.scope())
        adapter.shutdown()
        result = adapter.invoke(self.request(), {}, self.approved())
        self.assertEqual(ResultStatus.SHUTDOWN, result.status)


if __name__ == "__main__":
    unittest.main()
