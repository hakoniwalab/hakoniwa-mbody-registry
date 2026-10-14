import importlib.util
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BUILD_MODEL = ROOT / "bodies/hakoniwa_car2/config/build_model.py"
sys.path.insert(0, str(BUILD_MODEL.parent))
SPEC = importlib.util.spec_from_file_location("car2_build_model", BUILD_MODEL)
car2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(car2)


class Car2SuspensionTest(unittest.TestCase):
    def test_parameters_are_derived_from_sprung_mass(self):
        stiffness, damping, springref = car2.suspension_parameters()
        omega = 2 * math.pi * 1.35
        corner_mass = car2.SPRUNG_MASS_KG / 4
        self.assertAlmostEqual(stiffness, corner_mass * omega**2)
        self.assertAlmostEqual(damping, 2 * 0.35 * math.sqrt(stiffness * corner_mass))
        self.assertAlmostEqual(springref, -9.81 / omega**2)

    def test_front_steering_carriers_are_unsprung(self):
        self.assertEqual(car2.SPRUNG_MASS_KG, car2.CHASSIS_MASS_KG)

    def test_every_wheel_has_the_same_vertical_suspension(self):
        root = ET.fromstring(car2.model("default"))
        for corner in ("front_left", "front_right", "rear_left", "rear_right"):
            joint = root.find(f".//joint[@name='{corner}_suspension']")
            self.assertIsNotNone(joint, corner)
            self.assertEqual(joint.get("type"), "slide")
            self.assertEqual(joint.get("axis"), "0 0 1")
            self.assertEqual(joint.get("range"), "-0.08 0.08")
            self.assertEqual(joint.get("limited"), "true")

    def test_all_colour_variants_have_identical_suspension(self):
        expected = None
        for colour in car2.COLORS:
            root = ET.fromstring(car2.model(colour))
            actual = [
                tuple(sorted(joint.attrib.items()))
                for joint in root.findall(".//joint")
                if joint.get("name", "").endswith("_suspension")
            ]
            if expected is None:
                expected = actual
            self.assertEqual(actual, expected, colour)

    def test_steering_wheel_is_fixed_visual_only(self):
        root = ET.fromstring(car2.model("default"))
        body = root.find(".//body[@name='steering_wheel']")
        self.assertIsNotNone(body)
        assert body is not None
        self.assertIsNone(body.find("./joint"))
        self.assertIsNone(body.find("./inertial"))
        self.assertGreaterEqual(len(body.findall("./geom")), 20)
        for geom in body.findall("./geom"):
            self.assertEqual(geom.get("contype"), "0")
            self.assertEqual(geom.get("conaffinity"), "0")
            self.assertEqual(geom.get("density"), "0")


if __name__ == "__main__":
    unittest.main()
