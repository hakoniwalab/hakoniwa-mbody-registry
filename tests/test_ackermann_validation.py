import importlib.util
import math
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/ackermann/validate.py"
SPEC = importlib.util.spec_from_file_location("ackermann_validate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


GEOMETRY = {
    "wheelbase_m": 1.55,
    "track_width_m": 1.04,
    "wheel_radius_m": 0.25,
    "max_center_steering_rad": 0.70,
    "max_wheel_angular_velocity_rad_s": 20.0,
}


class AckermannKinematicsTest(unittest.TestCase):
    def test_straight_targets_are_equal(self):
        targets = VALIDATE.ackermann_targets(1.0, 0.0, GEOMETRY)
        self.assertEqual(targets["steering_left"], 0.0)
        self.assertEqual(targets["steering_right"], 0.0)
        self.assertEqual(targets["drive_left"], 4.0)
        self.assertEqual(targets["drive_right"], 4.0)

    def test_left_turn_has_inner_outer_geometry(self):
        targets = VALIDATE.ackermann_targets(2.0, 0.35, GEOMETRY)
        self.assertGreater(targets["steering_left"], targets["steering_right"])
        self.assertLess(targets["drive_left"], targets["drive_right"])

    def test_left_and_right_turns_are_mirrored(self):
        left = VALIDATE.ackermann_targets(2.0, 0.35, GEOMETRY)
        right = VALIDATE.ackermann_targets(2.0, -0.35, GEOMETRY)
        self.assertAlmostEqual(left["steering_left"], -right["steering_right"])
        self.assertAlmostEqual(left["steering_right"], -right["steering_left"])
        self.assertAlmostEqual(left["drive_left"], right["drive_right"])
        self.assertAlmostEqual(left["drive_right"], right["drive_left"])

    def test_wheel_velocity_is_clamped(self):
        targets = VALIDATE.ackermann_targets(100.0, 0.0, GEOMETRY)
        self.assertEqual(targets["drive_left"], 20.0)
        self.assertEqual(targets["drive_right"], 20.0)

    def test_quaternion_yaw(self):
        yaw = math.radians(30.0)
        quaternion = [math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0)]
        self.assertAlmostEqual(VALIDATE.yaw_from_qpos(quaternion), yaw)

    def test_user_weighted_score(self):
        loss, score, normalized = VALIDATE.weighted_score(
            {"steering": 0.05, "drive": 0.5},
            {"steering": 0.10, "drive": 1.0},
            {"steering": 2.0, "drive": 1.0},
        )
        self.assertAlmostEqual(normalized["steering"], 0.5)
        self.assertAlmostEqual(normalized["drive"], 0.5)
        self.assertAlmostEqual(loss, 0.5)
        self.assertAlmostEqual(score, 100.0 / 1.5)

    def test_unknown_score_metric_is_rejected(self):
        with self.assertRaises(VALIDATE.ValidationError):
            VALIDATE.weighted_score({"known": 1.0}, {"known": 1.0}, {"unknown": 1.0})


if __name__ == "__main__":
    unittest.main()
