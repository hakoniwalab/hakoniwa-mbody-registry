from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest

H = math.sqrt(0.5)  # exact unit quaternions (the generator does not normalise)


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hako_viewer_model_gen", ROOT / "tools/hako_viewer_model_gen.py"
)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


def quat_matrix(w: float, x: float, y: float, z: float) -> list[list[float]]:
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def rpy_matrix(roll: float, pitch: float, yaw: float) -> list[list[float]]:
    """R = Rz(yaw) Ry(pitch) Rx(roll), as the view-model's rpy is read."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


class QuatToRpyTest(unittest.TestCase):
    def assert_same_rotation(self, quat: tuple[float, float, float, float]) -> None:
        expected = quat_matrix(*quat)
        actual = rpy_matrix(*generator.quat_to_rpy(quat))
        for row in range(3):
            for col in range(3):
                self.assertAlmostEqual(actual[row][col], expected[row][col], places=9, msg=f"{quat}")

    def test_general_rotations(self) -> None:
        for quat in [
            (1.0, 0.0, 0.0, 0.0),
            (H, 0.0, 0.0, H),
            (0.5, 0.5, -0.5, 0.5),
            (0.0, 0.0, 1.0, 0.0),
        ]:
            self.assert_same_rotation(quat)

    def test_gimbal_lock_keeps_the_turn(self) -> None:
        # Pitch exactly -90 / +90 deg with a turn about the same axis (the
        # SO-101 upper arm mount is the first one): roll and yaw are coupled,
        # and both used to come out 0.
        for quat in [
            (0.5, -0.5, -0.5, -0.5),
            (0.5, 0.5, 0.5, 0.5),
            (H, 0.0, H, 0.0),
            (H, 0.0, -H, 0.0),
        ]:
            self.assert_same_rotation(quat)
        roll, pitch, yaw = generator.quat_to_rpy((0.5, -0.5, -0.5, -0.5))
        self.assertEqual(roll, 0.0)
        self.assertAlmostEqual(pitch, -math.pi / 2)
        self.assertAlmostEqual(yaw, -math.pi / 2)


if __name__ == "__main__":
    unittest.main()
