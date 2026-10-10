import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selma0_collaboration_intelligence_v1 import Selma0CollaborationIntelligenceV1, validate_turns
from selma0_tool_registry_android_v1 import Selma0ToolRegistryAndroidV1
from selma0_collaboration_intelligence_v1 import register_collaboration_tools
from selma0_permission_engine_android_v1 import Selma0PermissionEngineAndroidV1


def turn(speaker, act, artifact=False, confidence=1.0, evidence="none"):
    return {"speaker_id": speaker, "action_kind": act,
            "artifact_produced": artifact, "speaker_confidence": confidence,
            "evidence": evidence, "source_kind": "voice_transcript"}


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = Selma0CollaborationIntelligenceV1(self.tmp.name)

    def test_detects_reciprocity_loop_and_chooses_executor(self):
        events = [turn("gemini", "ack"), turn("chatgpt", "handoff"), turn("gemini", "ack")]
        outcome = self.engine.assess(events)
        self.assertIn("reciprocity_loop", outcome["flags"])
        self.assertEqual(outcome["next_action"], "assign_one_executor_and_request_specific_artifact")

    def test_artifact_breaks_deadlock(self):
        events = [turn("gemini", "ack"), turn("chatgpt", "deliver", True, evidence="test"), turn("gemini", "ack")]
        self.assertFalse(self.engine.assess(events)["loop_detected"])

    def test_does_not_claim_speaker_verification(self):
        flags = self.engine.assess([turn("unknown", "ask", confidence=0.4)])["flags"]
        self.assertIn("speaker_identity_uncertain", flags)

    def test_rejects_freeform_text_and_credentials(self):
        with self.assertRaises(ValueError):
            validate_turns([{**turn("user", "ask"), "transcript": "here is my secret"}])
        with self.assertRaises(ValueError):
            validate_turns([{**turn("user", "ask"), "api_key": "secret"}])

    def test_record_is_metadata_only_and_deduplicated(self):
        turns = [turn("gemini", "ack"), turn("chatgpt", "ack")]
        self.assertTrue(self.engine.record_observation(turns, "unproductive")["recorded"])
        self.assertFalse(self.engine.record_observation(turns, "unproductive")["recorded"])
        self.assertNotIn(b"gemini", (Path(self.tmp.name) / "observations.v1.sqlite3").read_bytes())

    def test_threshold_updates_are_bounded_and_revisioned(self):
        with self.assertRaises(ValueError):
            self.engine.apply_policy({"allow_external_effects": True}, 1)
        with self.assertRaises(ValueError):
            self.engine.apply_policy({"ack_streak_limit": 1}, 1)
        changed = self.engine.apply_policy({"ack_streak_limit": 2}, 1)
        self.assertEqual(changed["revision"], 2)
        with self.assertRaises(ValueError):
            self.engine.apply_policy({"ack_streak_limit": 4}, 1)

    def test_writes_require_command_core_approval(self):
        registry = Selma0ToolRegistryAndroidV1()
        register_collaboration_tools(registry)
        perms = Selma0PermissionEngineAndroidV1()
        for name in ("collab.record_observation", "collab.apply_policy"):
            descriptor = registry.describe(name)
            self.assertEqual(descriptor["risk"], "write")
            self.assertFalse(perms.evaluate(descriptor, approved=False).allowed)
        self.assertTrue(perms.evaluate(registry.describe("collab.assess"), approved=False).allowed)

    def test_candidate_policy_requires_three_independent_observations(self):
        for idx in range(3):
            turns = [turn(f"agent{idx}", "propose"), turn("gemini", "ack")]
            self.engine.record_observation(turns, "unproductive")
        result = self.engine.suggest_policy()
        self.assertEqual(result["suggested_updates"], {"ack_streak_limit": 2})
        self.assertFalse(result["applied"])


if __name__ == "__main__":
    unittest.main()
