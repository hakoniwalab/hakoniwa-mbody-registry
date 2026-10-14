from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hako_viewer_model_gen", ROOT / "tools/hako_viewer_model_gen.py"
)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


class ViewModelJointSourceTest(unittest.TestCase):
    def build(self, directory: Path, display_joint: dict) -> dict:
        model = directory / "model.xml"
        model.write_text(
            "<mujoco model='car'><worldbody><body name='vehicle'>"
            "<geom name='body_visual' type='box' size='.5 .5 .5'/>"
            "<body name='front_steer'><joint name='front_steer_joint' "
            "type='hinge' axis='0 0 1'/></body>"
            "<body name='steering_wheel' pos='.1 -.3 .7'>"
            "<geom name='wheel_visual' type='cylinder' size='.2 .01'/>"
            "</body></body></worldbody></mujoco>",
            encoding="utf-8",
        )
        recipe = {
            "format": "hako_viewer_model_recipe",
            "version": "0.1",
            "mjcf": str(model),
            "assets": {"glb_dir": "parts", "map": "body_name"},
            "base": "vehicle",
            "movable_joints": ["front_steer_joint"],
            "display_joints": [display_joint],
        }
        return generator.build_viewer_model(recipe, directory / "viewer.recipe.yaml")

    def test_display_joint_reuses_source_with_multiplier(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            result = self.build(Path(directory_name), {
                "name": "steering_wheel_joint",
                "body": "steering_wheel",
                "source_joint": "front_steer_joint",
                "multiplier": 15,
                "axis": [1, 0, 0],
            })
        [wheel] = [
            part for part in result["movable_parts"]
            if part["name"] == "steering_wheel"
        ]
        self.assertEqual(wheel["joint"], "steering_wheel_joint")
        self.assertEqual(wheel["source_joint"], "front_steer_joint")
        self.assertEqual(wheel["multiplier"], 15.0)
        self.assertEqual(wheel["motion"], {
            "type": "continuous",
            "axis": [1.0, 0.0, 0.0],
        })

    def test_display_joint_rejects_zero_multiplier(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            with self.assertRaisesRegex(generator.RecipeError, "finite and non-zero"):
                self.build(Path(directory_name), {
                    "name": "steering_wheel_joint",
                    "body": "steering_wheel",
                    "source_joint": "front_steer_joint",
                    "multiplier": 0,
                    "axis": [1, 0, 0],
                })


if __name__ == "__main__":
    unittest.main()
