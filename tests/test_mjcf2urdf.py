import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

import mujoco
import numpy as np


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
from mjcf2urdf import convert


ARM = """<mujoco model="test_arm">
  <compiler angle="radian"/>
  <default>
    <joint type="hinge" limited="true" range="-2 2"/>
    <default class="mount_joints">
      <joint axis="0 1 0"/>
      <default class="arm">
        <joint range="-1.1 1.6"/>
        <default class="wrist">
          <joint axis="1 0 0" range="-0.9 0.8"/>
        </default>
      </default>
    </default>
    <default class="slider">
      <joint type="slide" range="-0.1 0.1"/>
    </default>
  </default>
  <worldbody>
    <body name="mount" childclass="arm" pos="0.37 -0.43 0.8" quat="0.9 0.1 0.3 0.2">
      <body name="base" pos="0.13 0.12 -0.19" quat="0.93 -0.1 0.2 0.3">
        <body name="link1" pos="0.12 0.06 0.7" quat="0.8 0.1 0.2 -0.3">
          <joint name="j1"/>
          <geom type="sphere" size="0.03"/>
          <body name="link2" pos="0.22 -0.11 0.48" quat="0.7 -0.2 0.3 0.18">
            <joint name="j2" class="wrist" range="-0.78 0.74"/>
            <geom type="sphere" size="0.02"/>
            <body name="tip" pos="0.39 0.1 0.03" quat="0.97 -0.13 0.01 0.21"/>
          </body>
        </body>
        <body name="fixture" pos="0.05 0.02 0.1">
          <joint class="slider" name="slide"/>
          <geom type="sphere" size="0.03"/>
        </body>
      </body>
    </body>
  </worldbody>
</mujoco>
"""


def vector(text):
    return np.fromstring(text, dtype=float, sep=" ")


def rotation(axis, angle):
    unit = axis / np.linalg.norm(axis)
    x, y, z = unit
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    cosine, sine = math.cos(angle), math.sin(angle)
    return cosine * np.eye(3) + sine * cross + (1 - cosine) * np.outer(unit, unit)


class Mjcf2UrdfTest(unittest.TestCase):
    def assert_forward_kinematics(self, input_file, root_name, urdf):
        model = mujoco.MjModel.from_xml_path(str(input_file))
        data = mujoco.MjData(model)
        root_id = model.body(root_name).id
        body_ids = {root_id}
        for body_id, parent in enumerate(model.body_parentid):
            if parent in body_ids:
                body_ids.add(body_id)
        expected_links = {model.body(body_id).name for body_id in body_ids}
        self.assertEqual({link.get("name") for link in urdf.findall("link")}, expected_links)

        joints = []
        axes = np.eye(3)
        for joint in urdf.findall("joint"):
            origin = joint.find("origin")
            xyz = vector(origin.get("xyz"))
            roll, pitch, yaw = vector(origin.get("rpy"))
            orientation = rotation(axes[2], yaw) @ rotation(axes[1], pitch) @ rotation(axes[0], roll)
            joints.append((joint, xyz, orientation))

        rng = np.random.default_rng(476)
        max_position_error = 0.0
        max_rotation_error = 0.0
        for _ in range(50):
            data.qpos[:] = model.qpos0
            poses = {root_name: (np.zeros(3), np.eye(3))}
            for joint, xyz, orientation in joints:
                parent = joint.find("parent").get("link")
                child = joint.find("child").get("link")
                parent_xyz, parent_rotation = poses[parent]
                child_rotation = parent_rotation @ orientation
                if joint.get("type") == "revolute":
                    name = joint.get("name")
                    limit = joint.find("limit")
                    angle = rng.uniform(float(limit.get("lower")), float(limit.get("upper")))
                    data.joint(name).qpos[0] = angle
                    child_rotation = child_rotation @ rotation(vector(joint.find("axis").get("xyz")), angle)
                poses[child] = (parent_xyz + parent_rotation @ xyz, child_rotation)
            mujoco.mj_forward(model, data)
            root = data.body(root_name)
            world_to_root = root.xmat.reshape(3, 3).T
            for link, (xyz, orientation) in poses.items():
                body = data.body(link)
                expected_xyz = world_to_root @ (body.xpos - root.xpos)
                expected_rotation = world_to_root @ body.xmat.reshape(3, 3)
                position_error = np.linalg.norm(xyz - expected_xyz)
                rotation_error = np.max(np.abs(orientation - expected_rotation))
                self.assertLessEqual(position_error, 1e-5, f"Position of {link}")
                self.assertLessEqual(rotation_error, 1e-4, f"Rotation of {link}")
                max_position_error = max(max_position_error, position_error)
                max_rotation_error = max(max_rotation_error, rotation_error)
        return max_position_error, max_rotation_error

    def test_forward_kinematics_with_default_and_childclass(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "arm.xml"
            path.write_text(ARM, encoding="utf-8")
            urdf = ET.fromstring(convert(path, "base", "arm"))
            expected = {"j1": ("0 1 0", "-1.1", "1.6"), "j2": ("1 0 0", "-0.78", "0.74")}
            for name, (axis, lower, upper) in expected.items():
                joint = urdf.find(f"joint[@name='{name}']")
                self.assertEqual(joint.get("type"), "revolute")
                self.assertEqual(joint.find("axis").get("xyz"), axis)
                self.assertEqual(joint.find("limit").get("lower"), lower)
                self.assertEqual(joint.find("limit").get("upper"), upper)
            self.assertEqual(urdf.find("joint[@name='fixture_fixed']").get("type"), "fixed")
            self.assertFalse(urdf.findall(".//inertial"))
            self.assertFalse(urdf.findall(".//visual"))
            self.assertFalse(urdf.findall(".//collision"))
            self.assert_forward_kinematics(path, "base", urdf)

    def test_forward_kinematics_for_registry_body(self):
        path = REPO / "bodies/turtlebot3_waffle/generated/turtlebot3_waffle.xml"
        urdf = ET.fromstring(convert(path, "base_footprint", "waffle"))
        self.assertEqual(len(urdf.findall("joint[@type='revolute']")), 2)
        self.assert_forward_kinematics(path, "base_footprint", urdf)

    def test_cli_rejects_malformed_body_layouts(self):
        cases = (
            ('<body name="child"><joint name="a"/><joint name="b"/></body>', "more than one joint"),
            ('<body name="child"><joint name="a"/><joint name="b" type="slide"/></body>',
             "more than one joint"),
            ("<body/>", "Unnamed body"),
        )
        for child, expected in cases:
            with self.subTest(child=child), TemporaryDirectory() as temp:
                path = Path(temp) / "invalid.xml"
                path.write_text(f'<mujoco><worldbody><body name="base">{child}</body></worldbody></mujoco>',
                                encoding="utf-8")
                result = subprocess.run([sys.executable, "-B", str(TOOLS / "mjcf2urdf.py"), str(path), "base"],
                                        check=False, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Error:", result.stderr)
                self.assertIn(expected, result.stderr)
                self.assertFalse(path.with_suffix(".urdf").exists())

    def test_cli_defaults_to_generated_directory_for_registry_body(self):
        with TemporaryDirectory() as temp:
            body_dir = Path(temp) / "bodies" / "example"
            path = body_dir / "source" / "arm.xml"
            path.parent.mkdir(parents=True)
            path.write_text(ARM, encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(TOOLS / "mjcf2urdf.py"), str(path), "base",
                                     "--robot", "example"], check=True, capture_output=True, text=True)
            output = body_dir / "generated" / "arm.urdf"
            self.assertIn(str(output.resolve()), result.stdout)
            self.assertEqual(ET.parse(output).getroot().get("name"), "example")


if __name__ == "__main__":
    unittest.main()
