from __future__ import annotations

import unittest

from avatar.state import AvatarEvent, AvatarStateController, EventSource, TransitionStatus
from core.protocols import AvatarState


class AvatarStateControllerTests(unittest.TestCase):
    def test_ordered_generation_reaches_speaking(self):
        controller = AvatarStateController()
        self.assertTrue(controller.begin_generation("g1", 1).applied)
        result = controller.apply(AvatarEvent(2, AvatarState.SPEAKING, EventSource.MODEL, "g1"))
        self.assertTrue(result.applied); self.assertEqual(AvatarState.SPEAKING, result.state)

    def test_stale_sequence_is_rejected_without_state_change(self):
        controller = AvatarStateController(); controller.apply(AvatarEvent(5, AvatarState.LISTENING, EventSource.USER))
        result = controller.apply(AvatarEvent(4, AvatarState.IDLE, EventSource.USER))
        self.assertEqual(TransitionStatus.STALE_SEQUENCE, result.status); self.assertEqual(AvatarState.LISTENING, controller.state)

    def test_barge_in_cancels_generation_and_drains_audio(self):
        controller = AvatarStateController(); controller.begin_generation("g1", 1)
        controller.apply(AvatarEvent(2, AvatarState.SPEAKING, EventSource.MODEL, "g1"))
        result = controller.barge_in(3)
        self.assertEqual(AvatarState.LISTENING, result.state); self.assertIsNone(controller.active_generation)
        self.assertEqual(("cancel_generation", "drain_audio"), result.effects)

    def test_cancelled_generation_cannot_speak_later(self):
        controller = AvatarStateController(); controller.begin_generation("g1", 1); controller.barge_in(2)
        result = controller.apply(AvatarEvent(3, AvatarState.SPEAKING, EventSource.MODEL, "g1"))
        self.assertEqual(TransitionStatus.STALE_GENERATION, result.status); self.assertEqual(AvatarState.LISTENING, controller.state)

    def test_user_wins_same_sequence_batch_tie(self):
        controller = AvatarStateController(); controller.begin_generation("g1", 1)
        results = controller.apply_batch([
            AvatarEvent(2, AvatarState.SPEAKING, EventSource.MODEL, "g1"),
            AvatarEvent(2, AvatarState.INTERRUPTED, EventSource.USER),
        ])
        self.assertTrue(results[0].applied); self.assertEqual(("cancel_generation", "drain_audio"), results[0].effects)
        self.assertEqual(TransitionStatus.STALE_SEQUENCE, results[1].status); self.assertIsNone(controller.active_generation)
        self.assertEqual(AvatarState.LISTENING, controller.state)

    def test_completed_generation_is_cleared(self):
        controller = AvatarStateController(); controller.begin_generation("g1", 1)
        controller.apply(AvatarEvent(2, AvatarState.SPEAKING, EventSource.MODEL, "g1"))
        result = controller.apply(AvatarEvent(3, AvatarState.LISTENING, EventSource.MODEL, "g1"))
        self.assertTrue(result.applied); self.assertIsNone(controller.active_generation)

    def test_invalid_transition_fails_without_consuming_sequence(self):
        controller = AvatarStateController()
        invalid = controller.apply(AvatarEvent(1, AvatarState.SPEAKING, EventSource.USER))
        valid = controller.apply(AvatarEvent(1, AvatarState.LISTENING, EventSource.USER))
        self.assertEqual(TransitionStatus.INVALID, invalid.status); self.assertTrue(valid.applied)

    def test_kill_switch_emits_all_stop_effects_and_blocks_events(self):
        controller = AvatarStateController(); controller.begin_generation("g1", 1)
        result = controller.kill(2)
        self.assertFalse(controller.enabled)
        self.assertEqual({"cancel_generation", "drain_audio", "stop_animation", "stop_capture", "disable_autonomy"}, set(result.effects))
        blocked = controller.apply(AvatarEvent(3, AvatarState.LISTENING, EventSource.USER))
        self.assertEqual(TransitionStatus.DISABLED, blocked.status)

    def test_restart_is_explicit_quiet_idle(self):
        controller = AvatarStateController(); controller.kill(1)
        result = controller.restart(2)
        self.assertTrue(controller.enabled); self.assertEqual(AvatarState.IDLE, result.state); self.assertEqual(("remain_quiet",), result.effects)

    def test_restart_while_enabled_is_rejected(self):
        controller = AvatarStateController()
        self.assertEqual(TransitionStatus.INVALID, controller.restart(1).status)

    def test_event_validation_rejects_malformed_identity(self):
        with self.assertRaises(ValueError): AvatarEvent(-1, AvatarState.IDLE, EventSource.USER)
        with self.assertRaises(ValueError): AvatarEvent(1, AvatarState.IDLE, EventSource.MODEL, " ")

if __name__ == "__main__": unittest.main()
