"""Semantic rig contract for Selma Adult Mode renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

REQUIRED_BONES = (
    "hips",
    "spine",
    "chest",
    "neck",
    "head",
    "eye_left",
    "eye_right",
    "upper_arm_left",
    "lower_arm_left",
    "hand_left",
    "upper_arm_right",
    "lower_arm_right",
    "hand_right",
    "upper_leg_left",
    "lower_leg_left",
    "foot_left",
    "upper_leg_right",
    "lower_leg_right",
    "foot_right",
)

REQUIRED_BLENDSHAPES = (
    "blink_left",
    "blink_right",
    "jaw_open",
)

RECOMMENDED_VISEMES = (
    "sil",
    "aa",
    "ee",
    "ih",
    "oh",
    "ou",
    "fv",
    "th",
    "mbp",
    "l",
    "r",
    "wq",
)


@dataclass(frozen=True, slots=True)
class RigValidationReport:
    missing_bones: tuple[str, ...]
    missing_blendshapes: tuple[str, ...]
    duplicate_bone_targets: tuple[str, ...]
    duplicate_blendshape_targets: tuple[str, ...]
    missing_visemes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return (
            not self.missing_bones
            and not self.missing_blendshapes
            and not self.duplicate_bone_targets
            and not self.duplicate_blendshape_targets
        )


@dataclass(frozen=True, slots=True)
class RigBinding:
    bone_bindings: tuple[tuple[str, str], ...]
    blendshape_bindings: tuple[tuple[str, str], ...]
    viseme_bindings: tuple[tuple[str, str], ...] = ()
    height_meters: float = 1.70

    @classmethod
    def from_mappings(
        cls,
        bones: Mapping[str, str],
        blendshapes: Mapping[str, str],
        visemes: Mapping[str, str] | None = None,
        *,
        height_meters: float = 1.70,
    ) -> "RigBinding":
        if not 0.5 <= float(height_meters) <= 3.0:
            raise ValueError("height_meters is outside the supported humanoid range")
        return cls(
            bone_bindings=tuple(sorted((str(k), str(v)) for k, v in bones.items())),
            blendshape_bindings=tuple(
                sorted((str(k), str(v)) for k, v in blendshapes.items())
            ),
            viseme_bindings=tuple(
                sorted((str(k), str(v)) for k, v in (visemes or {}).items())
            ),
            height_meters=float(height_meters),
        )

    def validate(self) -> RigValidationReport:
        bones = dict(self.bone_bindings)
        blendshapes = dict(self.blendshape_bindings)
        visemes = dict(self.viseme_bindings)
        missing_bones = tuple(key for key in REQUIRED_BONES if not bones.get(key))
        missing_blendshapes = tuple(
            key for key in REQUIRED_BLENDSHAPES if not blendshapes.get(key)
        )
        duplicate_bones = _duplicates(value for value in bones.values() if value)
        duplicate_blendshapes = _duplicates(
            value for value in blendshapes.values() if value
        )
        missing_visemes = tuple(key for key in RECOMMENDED_VISEMES if not visemes.get(key))
        return RigValidationReport(
            missing_bones=missing_bones,
            missing_blendshapes=missing_blendshapes,
            duplicate_bone_targets=duplicate_bones,
            duplicate_blendshape_targets=duplicate_blendshapes,
            missing_visemes=missing_visemes,
        )

    def assert_valid(self) -> None:
        report = self.validate()
        if report.ok:
            return
        problems = []
        if report.missing_bones:
            problems.append("missing bones: " + ", ".join(report.missing_bones))
        if report.missing_blendshapes:
            problems.append(
                "missing blendshapes: " + ", ".join(report.missing_blendshapes)
            )
        if report.duplicate_bone_targets:
            problems.append(
                "duplicate bone targets: " + ", ".join(report.duplicate_bone_targets)
            )
        if report.duplicate_blendshape_targets:
            problems.append(
                "duplicate blendshape targets: "
                + ", ".join(report.duplicate_blendshape_targets)
            )
        raise ValueError("; ".join(problems))


def _duplicates(values) -> tuple[str, ...]:
    seen = set()
    duplicated = set()
    for value in values:
        if value in seen:
            duplicated.add(value)
        seen.add(value)
    return tuple(sorted(duplicated))
