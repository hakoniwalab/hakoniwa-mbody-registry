from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BUILD_MODEL = ROOT / "bodies/hakoniwa_truck/config/build_model.py"
sys.path.insert(0, str(BUILD_MODEL.parent))
SPEC = importlib.util.spec_from_file_location("truck_build_model", BUILD_MODEL)
truck = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(truck)


class TruckSuspensionTest(unittest.TestCase):
    def test_corner_masses_follow_static_axle_load(self) -> None:
        front, rear = truck.corner_sprung_masses()
        self.assertAlmostEqual(2 * (front + rear), truck.SPRUNG_MASS_KG)
        expected_front_axle = truck.SPRUNG_MASS_KG * 1.55 / 4.30
        self.assertAlmostEqual(front * 2, expected_front_axle)
        self.assertGreater(rear, front)

    def test_parameters_are_derived_for_each_axle(self) -> None:
        omega = 2 * math.pi * truck.SUSPENSION_NATURAL_FREQUENCY_HZ
        front_mass, rear_mass = truck.corner_sprung_masses()
        for axle, mass in (("front", front_mass), ("rear", rear_mass)):
            stiffness, damping, springref = truck.suspension_parameters(axle)
            self.assertAlmostEqual(stiffness, mass * omega**2)
            self.assertAlmostEqual(
                damping,
                2 * truck.SUSPENSION_DAMPING_RATIO * math.sqrt(stiffness * mass),
            )
            self.assertAlmostEqual(springref, -truck.GRAVITY_M_S2 / omega**2)

    def test_all_wheels_have_vertical_suspension(self) -> None:
        root = ET.fromstring(truck.model("default"))
        for corner in ("front_left", "front_right", "rear_left", "rear_right"):
            joint = root.find(f".//joint[@name='{corner}_suspension']")
            self.assertIsNotNone(joint, corner)
            assert joint is not None
            self.assertEqual(joint.get("type"), "slide")
            self.assertEqual(joint.get("axis"), "0 0 1")
            self.assertEqual(joint.get("range"), "-0.1 0.1")
            self.assertEqual(joint.get("limited"), "true")

    def test_rear_springs_are_stiffer_than_front_springs(self) -> None:
        root = ET.fromstring(truck.model("default"))
        front = root.find(".//joint[@name='front_left_suspension']")
        rear = root.find(".//joint[@name='rear_left_suspension']")
        assert front is not None and rear is not None
        self.assertGreater(float(rear.get("stiffness", "0")), float(front.get("stiffness", "0")))

    def test_all_colour_variants_have_identical_suspension(self) -> None:
        expected = None
        for colour in truck.CAB_COLORS:
            root = ET.fromstring(truck.model(colour))
            actual = [
                tuple(sorted(joint.attrib.items()))
                for joint in root.findall(".//joint")
                if joint.get("name", "").endswith("_suspension")
            ]
            if expected is None:
                expected = actual
            self.assertEqual(actual, expected, colour)


if __name__ == "__main__":
    unittest.main()
