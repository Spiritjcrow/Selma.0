from __future__ import annotations

from copy import deepcopy
import json
import socket
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from adapters.null import NullAdapter
from core.bootstrap import OfflineCore, RuntimeState
from core.protocols import (
    ALL_CAPABILITIES,
    CAPABILITY_RISK_FLOORS,
    CONTRACT_VERSION,
    AdapterDescriptor,
    AdapterResult,
    Capability,
    CapabilityAdapter,
    CancellationToken,
    InvocationContext,
    ResultStatus,
    RiskClass,
    SupportState,
)
from tools.generate_support_matrix import (
    ALLOWED_STATES,
    ARCHITECTURE_MANIFEST,
    OUTPUT,
    load_json,
    load_inputs,
    render_matrix,
    validate_architecture,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


class NullAdapterContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = NullAdapter(Capability.MODEL)

    def invoke(self, context: InvocationContext) -> AdapterResult:
        return self.adapter.invoke("generate", {"prompt": "hello"}, context)

    def approved(
        self,
        request_id: str,
        *,
        operation: str = "generate",
        timeout_seconds: float | None = None,
        cancellation: CancellationToken | None = None,
    ) -> InvocationContext:
        return InvocationContext.approved_call(
            request_id,
            capability=Capability.MODEL,
            operation=operation,
            timeout_seconds=timeout_seconds,
            cancellation=cancellation,
        )

    def test_implements_generic_capability_protocol(self) -> None:
        self.assertIsInstance(self.adapter, CapabilityAdapter)
        self.assertEqual(CONTRACT_VERSION, self.adapter.descriptor.contract_version)

    def test_unavailable_never_reports_success(self) -> None:
        result = self.invoke(self.approved("unavailable"))
        self.assertEqual(ResultStatus.UNAVAILABLE, result.status)
        self.assertFalse(result.ok)

    def test_permission_denial_fails_before_unavailable_result(self) -> None:
        result = self.invoke(InvocationContext(request_id="denied"))
        self.assertEqual(ResultStatus.DENIED, result.status)
        self.assertFalse(result.ok)

    def test_cancellation_fails_before_adapter_work(self) -> None:
        token = CancellationToken()
        token.cancel()
        context = self.approved("cancelled", cancellation=token)
        result = self.invoke(context)
        self.assertEqual(ResultStatus.CANCELLED, result.status)
        self.assertFalse(result.ok)

    def test_expired_deadline_fails_closed(self) -> None:
        context = self.approved("expired", timeout_seconds=0)
        result = self.invoke(context)
        self.assertEqual(ResultStatus.TIMED_OUT, result.status)
        self.assertFalse(result.ok)

    def test_shutdown_fails_closed(self) -> None:
        self.adapter.shutdown()
        result = self.invoke(self.approved("shutdown"))
        self.assertEqual(ResultStatus.SHUTDOWN, result.status)
        self.assertFalse(result.ok)

    def test_no_null_path_can_construct_success(self) -> None:
        contexts = [
            InvocationContext(request_id="denied"),
            self.approved("unavailable"),
            self.approved("expired", timeout_seconds=0),
        ]
        statuses = {self.invoke(context).status for context in contexts}
        self.assertNotIn(ResultStatus.SUCCESS, statuses)

    def test_approval_is_bound_to_one_capability_and_operation(self) -> None:
        context = self.approved("scoped")
        wrong_operation = self.adapter.invoke("embed", {}, context)
        wrong_capability = NullAdapter(Capability.MEMORY).invoke("generate", {}, context)
        self.assertEqual(ResultStatus.DENIED, wrong_operation.status)
        self.assertEqual(ResultStatus.DENIED, wrong_capability.status)

    def test_context_rejects_empty_identity_and_unbounded_deadlines(self) -> None:
        with self.assertRaises(ValueError):
            InvocationContext(request_id=" ")
        with self.assertRaises(ValueError):
            self.approved("empty-operation", operation=" ")
        for timeout in (-1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.approved("invalid-timeout", timeout_seconds=timeout)

    def test_null_descriptors_preserve_capability_risk_floors(self) -> None:
        for capability in ALL_CAPABILITIES:
            with self.subTest(capability=capability):
                self.assertEqual(
                    CAPABILITY_RISK_FLOORS[capability],
                    NullAdapter(capability).descriptor.risk_class,
                )

    def test_descriptor_rejects_risk_below_capability_floor(self) -> None:
        with self.assertRaises(ValueError):
            AdapterDescriptor(
                adapter_id="unsafe.network.v1",
                capability=Capability.NETWORK,
                platform="test",
                support_state=SupportState.PLANNED,
                risk_class=RiskClass.READ,
            )

    def test_context_and_descriptor_reject_malformed_types(self) -> None:
        with self.assertRaises(TypeError):
            InvocationContext(request_id="invalid-deadline", deadline_monotonic=True)
        with self.assertRaises(ValueError):
            AdapterDescriptor(
                adapter_id=None,  # type: ignore[arg-type]
                capability=Capability.MODEL,
                platform="test",
                support_state=SupportState.PLANNED,
                risk_class=RiskClass.READ,
            )


class OfflineBootstrapContractTests(unittest.TestCase):
    def test_core_boots_offline_with_honest_degraded_status(self) -> None:
        with (
            patch.object(socket, "create_connection", side_effect=AssertionError("network used")),
            patch.object(urllib.request, "urlopen", side_effect=AssertionError("network used")),
        ):
            core = OfflineCore()
            health = core.boot()
        self.assertEqual(RuntimeState.RUNNING, health.state)
        self.assertTrue(health.offline)
        self.assertEqual(
            {capability.value for capability in ALL_CAPABILITIES},
            set(health.capability_status),
        )
        self.assertEqual(
            {ResultStatus.UNAVAILABLE.value},
            set(health.capability_status.values()),
        )

    def test_network_enable_is_explicitly_rejected_by_null_bootstrap(self) -> None:
        with self.assertRaises(ValueError):
            OfflineCore().boot(allow_network=True)

    def test_shutdown_is_visible_and_irreversible(self) -> None:
        core = OfflineCore()
        core.boot()
        health = core.shutdown()
        self.assertEqual(RuntimeState.STOPPED, health.state)
        result = core.adapter(Capability.DEVICE).invoke(
            "read",
            {},
            InvocationContext.approved_call(
                "after-shutdown",
                capability=Capability.DEVICE,
                operation="read",
            ),
        )
        self.assertEqual(ResultStatus.SHUTDOWN, result.status)
        self.assertEqual(
            {ResultStatus.SHUTDOWN.value},
            set(health.capability_status.values()),
        )
        with self.assertRaises(RuntimeError):
            core.boot()


class ArchitectureManifestContractTests(unittest.TestCase):
    def test_manifest_is_versioned_and_preserves_single_control_plane(self) -> None:
        architecture = json.loads(ARCHITECTURE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(1, architecture["schema_version"])
        self.assertEqual("gate1-1.0.0", architecture["architecture_version"])
        control_plane = architecture["single_control_plane"]
        for key in ("tool_registry", "permission_policy", "router", "audit"):
            self.assertTrue((ROOT / control_plane[key]).is_file(), key)
        self.assertIn("cannot authorize external effects", control_plane["rule"])
        for item in architecture["capabilities"]:
            self.assertEqual(
                CAPABILITY_RISK_FLOORS[Capability(item["id"])],
                RiskClass(item["risk_floor"]),
            )

    def test_adapter_manifests_cover_every_capability(self) -> None:
        architecture, manifests = load_inputs()
        expected = {item["id"] for item in architecture["capabilities"]}
        by_platform = {item["platform_id"]: item for item in manifests}
        self.assertIn("portable-null", by_platform)
        self.assertIn("android-termux", by_platform)
        self.assertIn("linux-chromeos", by_platform)
        for manifest in manifests:
            self.assertEqual(expected, set(manifest["capabilities"]))
            for record in manifest["capabilities"].values():
                self.assertIn(record["state"], ALLOWED_STATES)
                self.assertTrue(record["evidence"])

    def test_desktop_contract_does_not_claim_unimplemented_success(self) -> None:
        _, manifests = load_inputs()
        linux = next(item for item in manifests if item["platform_id"] == "linux-chromeos")
        self.assertEqual(
            {"planned"},
            {record["state"] for record in linux["capabilities"].values()},
        )

    def test_android_contract_separates_portable_and_owned_device_evidence(self) -> None:
        _, manifests = load_inputs()
        android = next(item for item in manifests if item["platform_id"] == "android-termux")
        self.assertIn("No owned-Android result is claimed", android["evidence_scope"])
        self.assertEqual("planned", android["capabilities"]["model"]["state"])
        self.assertEqual("tested", android["capabilities"]["device"]["state"])

    def test_generated_support_matrix_is_current(self) -> None:
        self.assertTrue(OUTPUT.is_file())
        self.assertEqual(render_matrix(), OUTPUT.read_text(encoding="utf-8"))

    def test_architecture_validation_rejects_duplicate_capabilities(self) -> None:
        architecture = json.loads(ARCHITECTURE_MANIFEST.read_text(encoding="utf-8"))
        architecture["capabilities"].append(deepcopy(architecture["capabilities"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate architecture capability"):
            validate_architecture(architecture)

    def test_manifest_validation_rejects_blank_evidence(self) -> None:
        architecture, manifests = load_inputs()
        capabilities = validate_architecture(architecture)
        manifest = deepcopy(manifests[0])
        manifest["capabilities"][capabilities[0]]["evidence"] = " "
        with self.assertRaisesRegex(ValueError, "evidence must be a non-empty string"):
            validate_manifest(manifest, capabilities, source="test-manifest")

    def test_json_loader_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version": 1, "schema_version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
