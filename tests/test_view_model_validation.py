from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_view_model", ROOT / "tools/validate_view_model.py"
)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class ViewModelValidationTest(unittest.TestCase):
    def test_transform_only_movable_pivot_is_valid(self) -> None:
        model = {
            "format": "hako_viewer_model",
            "version": "0.1",
            "coordinate_system": "mujoco",
            "robot": {"name": "car", "root": "vehicle"},
            "assets": [
                {"id": "vehicle", "type": "glb", "path": "vehicle.glb"},
            ],
            "base": {
                "name": "vehicle",
                "asset": "vehicle",
                "mount": {"xyz": [0, 0, 0], "rpy": [0, 0, 0]},
            },
            "movable_parts": [{
                "name": "steering_pivot",
                "joint": "steering_joint",
                "parent": "vehicle",
                "mount": {"xyz": [1, 0, 0], "rpy": [0, 0, 0]},
                "motion": {"type": "continuous", "axis": [0, 0, 1]},
            }],
        }
        validator.validate_view_model(model)


if __name__ == "__main__":
    unittest.main()
