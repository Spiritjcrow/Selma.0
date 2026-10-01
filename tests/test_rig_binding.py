import unittest

from core.rig_binding import (
    REQUIRED_BLENDSHAPES,
    REQUIRED_BONES,
    RECOMMENDED_VISEMES,
    RigBinding,
)


class RigTests(unittest.TestCase):
    def complete(self):
        bones = {key: "Bone_" + key for key in REQUIRED_BONES}
        shapes = {key: "Shape_" + key for key in REQUIRED_BLENDSHAPES}
        visemes = {key: "Viseme_" + key for key in RECOMMENDED_VISEMES}
        return bones, shapes, visemes

    def test_complete_rig_passes(self):
        bones, shapes, visemes = self.complete()
        rig = RigBinding.from_mappings(bones, shapes, visemes)
        self.assertTrue(rig.validate().ok)
        rig.assert_valid()

    def test_missing_eye_fails(self):
        bones, shapes, visemes = self.complete()
        del bones["eye_left"]
        report = RigBinding.from_mappings(bones, shapes, visemes).validate()
        self.assertFalse(report.ok)
        self.assertIn("eye_left", report.missing_bones)

    def test_duplicate_bone_target_fails(self):
        bones, shapes, visemes = self.complete()
        bones["head"] = bones["neck"]
        report = RigBinding.from_mappings(bones, shapes, visemes).validate()
        self.assertFalse(report.ok)
        self.assertIn(bones["neck"], report.duplicate_bone_targets)

    def test_visemes_recommended_not_hard_required(self):
        bones, shapes, _ = self.complete()
        report = RigBinding.from_mappings(bones, shapes, {}).validate()
        self.assertTrue(report.ok)
        self.assertEqual(set(RECOMMENDED_VISEMES), set(report.missing_visemes))


if __name__ == "__main__":
    unittest.main()
