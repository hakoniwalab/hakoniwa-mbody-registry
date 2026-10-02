import importlib.util
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
SPEC = importlib.util.spec_from_file_location("glb_add_lights", TOOLS / "glb_add_lights.py")
LIGHTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LIGHTS
SPEC.loader.exec_module(LIGHTS)


def rotate(q, v):
    x, y, z, w = q
    # v' = q v q*
    ix = w * v[0] + y * v[2] - z * v[1]
    iy = w * v[1] + z * v[0] - x * v[2]
    iz = w * v[2] + x * v[1] - y * v[0]
    iw = -x * v[0] - y * v[1] - z * v[2]
    return (ix * w + iw * -x + iy * -z - iz * -y,
            iy * w + iw * -y + iz * -x - ix * -z,
            iz * w + iw * -z + ix * -y - iy * -x)


class GlbAddLightsTest(unittest.TestCase):
    def test_a_spot_points_along_its_direction(self):
        for direction in ((1, 0, 0), (1, 0, -0.12), (0, 1, 0), (0, 0, -1), (0, 0, 1)):
            q = LIGHTS.rotation_to(direction)
            got = rotate(q, (0.0, 0.0, -1.0))
            norm = math.sqrt(sum(c * c for c in direction))
            for a, b in zip(got, direction):
                self.assertAlmostEqual(a, b / norm, places=5)  # rotations are rounded to 6 decimals

    def test_matching_materials_glow_and_lamps_join_their_part(self):
        document = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
                    "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [0.25, 0.65, 1.0, 1.0]}},
                                  {"pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1.0]}}]}
        directory = Path(tempfile.mkdtemp())
        (directory / "vehicle.glb").write_bytes(LIGHTS.write_glb(document, b""))
        report = LIGHTS.apply(directory, {
            "glow": [{"rgba": [0.25, 0.65, 1.0], "emissive": [0.1, 0.45, 1.0], "strength": 2.0}],
            "lights": [{"part": "vehicle", "type": "spot", "position": [1, 0, 0.2], "direction": [1, 0, 0],
                        "intensity": 40, "range": 20}],
        })
        self.assertEqual(report["vehicle.glb"], {"glowing_materials": 1, "lights": 1})
        result, _ = LIGHTS.read_glb((directory / "vehicle.glb").read_bytes())
        self.assertEqual(result["materials"][0]["emissiveFactor"], [0.1, 0.45, 1.0])
        self.assertNotIn("emissiveFactor", result["materials"][1])
        self.assertEqual(result["extensions"]["KHR_lights_punctual"]["lights"][0]["type"], "spot")
        self.assertIn(1, result["scenes"][0]["nodes"])
        self.assertIn("KHR_materials_emissive_strength", result["extensionsUsed"])

    def test_lights_for_a_missing_part_are_an_error(self):
        directory = Path(tempfile.mkdtemp())
        with self.assertRaises(LIGHTS.LightsError):
            LIGHTS.apply(directory, {"lights": [{"part": "nothing", "position": [0, 0, 0]}]})


if __name__ == "__main__":
    unittest.main()
