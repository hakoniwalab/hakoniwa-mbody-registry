import importlib.util
import numpy as np
from pathlib import Path
import sys
import trimesh
import unittest
import xml.etree.ElementTree as ET


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "mjcf2glb.py"
SPEC = importlib.util.spec_from_file_location("mjcf2glb", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MJCF2GLB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MJCF2GLB
SPEC.loader.exec_module(MJCF2GLB)


class Mjcf2GlbTest(unittest.TestCase):
    def test_ros_to_three_transform_maps_forward_left_up(self):
        transform = MJCF2GLB.ros_to_three_transform()
        forward = transform @ [1, 0, 0, 1]
        left = transform @ [0, 1, 0, 1]
        up = transform @ [0, 0, 1, 1]

        self.assertEqual(forward[:3].tolist(), [0.0, 0.0, -1.0])
        self.assertEqual(left[:3].tolist(), [-1.0, 0.0, 0.0])
        self.assertEqual(up[:3].tolist(), [0.0, 1.0, 0.0])

    def test_visible_only_skips_explicitly_transparent_geom(self):
        transparent = ET.fromstring('<geom name="contact" type="box" rgba="1 0 0 0"/>')
        visible = ET.fromstring('<geom name="frame" type="box" rgba="1 0 0 1"/>')

        self.assertIsNone(
            MJCF2GLB.parse_geom(transparent, 0, "body", {}, True, True)
        )
        self.assertIsNotNone(
            MJCF2GLB.parse_geom(visible, 1, "body", {}, True, True)
        )

    def test_default_keeps_transparent_geom_for_backward_compatibility(self):
        transparent = ET.fromstring('<geom name="contact" type="box" rgba="1 0 0 0"/>')

        self.assertIsNotNone(
            MJCF2GLB.parse_geom(transparent, 0, "body", {}, True)
        )

    def test_capsule_without_fromto_is_centered_on_geom_origin(self):
        geom = MJCF2GLB.parse_geom(
            ET.fromstring(
                '<geom name="skid" type="capsule" size="0.0125 0.31"/>'
            ),
            0,
            "body",
            {},
            True,
        )

        mesh = MJCF2GLB.create_geometry(trimesh, geom, False)

        np.testing.assert_allclose(mesh.bounds.mean(axis=0), [0.0, 0.0, 0.0])

    def test_capsule_fromto_is_centered_between_endpoints(self):
        geom = MJCF2GLB.parse_geom(
            ET.fromstring(
                '<geom name="link" type="capsule" size="0.01" '
                'fromto="1 2 3 5 2 3"/>'
            ),
            0,
            "body",
            {},
            True,
        )

        mesh = MJCF2GLB.create_geometry(trimesh, geom, False)

        np.testing.assert_allclose(
            mesh.bounds.mean(axis=0), [3.0, 2.0, 3.0], atol=1e-12
        )


if __name__ == "__main__":
    unittest.main()
