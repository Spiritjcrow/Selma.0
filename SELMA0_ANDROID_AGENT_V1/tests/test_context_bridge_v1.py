import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selma0_context_bridge_v1 import (
    BridgeError, LocalHandoffBridge, ReplayLedger, PROTOCOL, ROUTE,
    infer_context, make_signed_headers, signature,
)
from selma0_collaboration_intelligence_v1 import Selma0CollaborationIntelligenceV1

FIXED_NOW = 1800000000
KEY = b"q" * 32


def make_body(text="Please implement SelmaOS context routing.", **changes):
    body = {"protocol": PROTOCOL, "recipient": "selma", "sender_claim": "gemini",
            "message_id": str(uuid.uuid4()), "conversation_id": str(uuid.uuid4()),
            "text": text}
    body.update(changes)
    return json.dumps(body).encode()


class ContextBridgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ledger = ReplayLedger(Path(temp.name) / "ledger", clock=lambda: FIXED_NOW)
        self.bridge = LocalHandoffBridge(ledger=self.ledger, clock=lambda: FIXED_NOW)
        self.engine = Selma0CollaborationIntelligenceV1(Path(temp.name) / "collab")
        self.key_patch = patch.dict(os.environ, {"SELMA0_BRIDGE_HMAC_KEY_V1": KEY.hex()})
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)

    def signed(self, data, timestamp=FIXED_NOW, nonce=None):
        return make_signed_headers(data, KEY, timestamp, nonce)

    def assess(self, turns):
        return self.engine.assess(turns)

    def test_1_verified_signed_message_is_analyzed_not_executed(self):
        data = make_body()
        self.assertTrue(self.bridge.verify(self.signed(data), data))
        output = self.bridge.process(data, self.assess)
        self.assertEqual(output["context"]["intent"], "implementation")
        self.assertEqual(output["authentication"], "shared_key_client_only_not_model_or_voice_identity")
        self.assertTrue(output["assessment"]["speaker_ambiguity"])
        self.assertFalse(output["context"]["executes_instructions"])
        self.assertFalse((self.engine.data_dir / "observations.v1.sqlite3").exists())

    def test_2_tampered_message_rejected(self):
        data = make_body()
        with self.assertRaisesRegex(BridgeError, "signature"):
            self.bridge.verify(self.signed(data), data + b" ")

    def test_3_nonce_cannot_be_replayed_across_restored_processes(self):
        data = make_body()
        headers = self.signed(data)
        self.bridge.verify(headers, data)
        restarted = LocalHandoffBridge(
            ledger=ReplayLedger(self.ledger.root, clock=lambda: FIXED_NOW),
            clock=lambda: FIXED_NOW)
        with self.assertRaisesRegex(BridgeError, "replayed"):
            restarted.verify(headers, data)

    def test_4_stale_timestamp_rejected(self):
        data = make_body()
        with self.assertRaisesRegex(BridgeError, "expired"):
            self.bridge.verify(self.signed(data, FIXED_NOW - 121), data)

    def test_5_missing_key_denies_requests(self):
        with patch.dict(os.environ, {"SELMA0_BRIDGE_HMAC_KEY_V1": ""}):
            data = make_body()
            with self.assertRaisesRegex(BridgeError, "disabled"):
                self.bridge.verify(self.signed(data), data)

    def test_6_credentials_and_arbitrary_fields_rejected(self):
        for data in (
            make_body("API_KEY=verysecret123456"),
            make_body("Here is my token", password="secret"),
        ):
            with self.subTest(data=data):
                with self.assertRaises(BridgeError):
                    self.bridge.process(data, self.assess)

    def test_7_body_size_and_method_limited(self):
        huge = b"x" * 9000
        with self.assertRaises(BridgeError):
            self.bridge.verify(self.signed(huge), huge)
        data = make_body()
        with self.assertRaises(BridgeError):
            self.bridge.verify(self.signed(data), data, method="GET")

    def test_8_origin_claim_is_not_proof_of_identity(self):
        out = self.bridge.process(make_body("Understood."), self.assess)
        self.assertEqual(out["sender_claim"], "gemini")
        self.assertIn("speaker_identity_uncertain", out["assessment"]["flags"])

    def test_9_prior_metadata_helps_find_reciprocity_loop(self):
        prior = [
            {"speaker_id": "gemini", "action_kind": "ack", "source_kind": "import"},
            {"speaker_id": "chatgpt", "action_kind": "handoff", "source_kind": "import"},
        ]
        result = self.bridge.process(make_body("Okay.", previous_turns=prior), self.assess)
        self.assertTrue(result["assessment"]["loop_detected"])

    def test_10_malformed_sender_rejected_safely(self):
        with self.assertRaises(BridgeError):
            self.bridge.process(make_body(sender_claim="untrusted_agent"), self.assess)

    def test_11_signature_binds_exact_route(self):
        data = make_body()
        headers = self.signed(data)
        headers["X-Selma-Signature"] = signature(KEY, str(FIXED_NOW),
                                                     headers["X-Selma-Nonce"],
                                                     data, path="/other")
        with self.assertRaisesRegex(BridgeError, "signature"):
            self.bridge.verify(headers, data)

    def test_13_network_bound_bridge_route_refuses_requests(self):
        from selma0_runtime_command_core_android_v1 import (
            HANDOFF_ROUTE_V1, Selma0CommandCoreHTTPAndroidV1,
        )
        handler = object.__new__(Selma0CommandCoreHTTPAndroidV1)
        handler.path = HANDOFF_ROUTE_V1
        handler.headers = {"Host": "127.0.0.1:8765"}
        handler.server = SimpleNamespace(server_address=("0.0.0.0", 8765))
        responses = []
        handler.send_json = lambda status, body: responses.append((status, body))
        handler.do_POST()
        self.assertEqual(responses[0][0], 403)
        self.assertIn("loopback", responses[0][1]["error"])

    def test_12_acknowledgment_vs_action(self):
        self.assertEqual(infer_context("Thank you!")["action_kind"], "ack")
        self.assertEqual(infer_context("Please implement routing")["intent"], "implementation")


if __name__ == "__main__":
    unittest.main()
