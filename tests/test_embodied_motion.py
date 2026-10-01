import unittest

from core.embodied_motion import EyesFirstMotionController


class MotionTests(unittest.TestCase):
    def test_eyes_lead_head(self):
        controller = EyesFirstMotionController()
        pose = controller.tick(0.05, gaze_x=1.0)
        self.assertGreater(pose.eye_x, 0.5)
        self.assertAlmostEqual(pose.head_yaw_deg, 0.0, places=6)
        for _ in range(4):
            pose = controller.tick(0.05, gaze_x=1.0)
        self.assertGreater(pose.head_yaw_deg, 0.0)

    def test_bounds(self):
        controller = EyesFirstMotionController()
        pose = controller.tick(
            0.5,
            gaze_x=99,
            gaze_y=-99,
            speaking=True,
            mouth_open=99,
        )
        self.assertLessEqual(abs(pose.eye_x), 1)
        self.assertLessEqual(abs(pose.head_yaw_deg), 18)
        self.assertLessEqual(abs(pose.head_pitch_deg), 12)
        self.assertEqual(pose.jaw_open, 1)

    def test_blink_occurs(self):
        controller = EyesFirstMotionController()
        maximum = 0
        for _ in range(600):
            pose = controller.tick(0.01)
            maximum = max(maximum, pose.blink)
        self.assertGreater(maximum, 0.9)

    def test_deterministic(self):
        left = EyesFirstMotionController()
        right = EyesFirstMotionController()
        for _ in range(100):
            left_pose = left.tick(
                0.016,
                gaze_x=0.4,
                gaze_y=-0.2,
                speaking=True,
                mouth_open=0.3,
            )
            right_pose = right.tick(
                0.016,
                gaze_x=0.4,
                gaze_y=-0.2,
                speaking=True,
                mouth_open=0.3,
            )
            self.assertEqual(left_pose, right_pose)


if __name__ == "__main__":
    unittest.main()
