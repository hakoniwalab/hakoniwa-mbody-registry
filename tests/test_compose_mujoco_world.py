import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/compose_mujoco_world.py"
SPEC = importlib.util.spec_from_file_location("compose_mujoco_world", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
COMPOSE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPOSE)


class ComposeMujocoWorldTest(unittest.TestCase):
    def test_merges_world_into_robot_and_rewrites_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            robot_dir = root / "robot"
            world_dir = root / "world"
            output_dir = root / "output"
            robot_dir.mkdir()
            world_dir.mkdir()
            output_dir.mkdir()

            robot_mesh = robot_dir / "meshes" / "robot.obj"
            robot_mesh.parent.mkdir()
            robot_mesh.write_text("robot", encoding="utf-8")
            world_mesh = world_dir / "city.obj"
            world_mesh.write_text("city", encoding="utf-8")

            robot_xml = robot_dir / "robot.xml"
            robot_xml.write_text(
                """<mujoco model='robot'>
  <compiler angle='radian' meshdir='meshes'/>
  <size nstack='1000' nconmax='200'/>
  <asset><mesh name='robot_mesh' file='robot.obj'/></asset>
  <worldbody>
    <geom name='ground' type='plane' size='10 10 .1'/>
    <body name='vehicle'><freejoint name='base_freejoint'/><geom name='robot_geom' type='box' size='.5 .5 .5'/></body>
  </worldbody>
  <actuator><motor name='drive' joint='base_freejoint'/></actuator>
  <contact><exclude body1='vehicle' body2='vehicle'/></contact>
</mujoco>""",
                encoding="utf-8",
            )
            world_xml = world_dir / "world.xml"
            world_xml.write_text(
                """<mujoco model='world'>
  <option timestep='0.01'/>
  <size nstack='5000' njmax='10000'/>
  <asset><mesh name='city_mesh' file='city.obj'/></asset>
  <worldbody>
    <geom name='city_ground' type='plane' size='20 20 .1'/>
    <body name='building'><geom name='building_geom' type='mesh' mesh='city_mesh'/></body>
  </worldbody>
</mujoco>""",
                encoding="utf-8",
            )
            output = output_dir / "composed.xml"

            receipt = COMPOSE.compose_mujoco_world(robot_xml, world_xml, output)

            self.assertEqual(receipt["removed_robot_ground_geoms"], 1)
            self.assertEqual(receipt["merged_size"], {"nstack": "5000", "njmax": "10000"})
            self.assertEqual(receipt["added_world_assets"], 1)
            self.assertEqual(receipt["added_worldbody_children"], 2)
            self.assertEqual(receipt["ignored_world_sections"], ["option"])

            tree = ET.parse(output)
            composed = tree.getroot()
            compiler = composed.find("compiler")
            assert compiler is not None
            self.assertNotIn("meshdir", compiler.attrib)

            size = composed.find("size")
            assert size is not None
            self.assertEqual(size.get("nstack"), "5000")
            self.assertEqual(size.get("nconmax"), "200")
            self.assertEqual(size.get("njmax"), "10000")

            asset = composed.find("asset")
            assert asset is not None
            robot_asset = asset.find("mesh[@name='robot_mesh']")
            city_asset = asset.find("mesh[@name='city_mesh']")
            assert robot_asset is not None and city_asset is not None
            self.assertEqual((output.parent / robot_asset.get("file")).resolve(), robot_mesh.resolve())
            self.assertEqual((output.parent / city_asset.get("file")).resolve(), world_mesh.resolve())

            worldbody = composed.find("worldbody")
            assert worldbody is not None
            self.assertIsNone(worldbody.find("geom[@name='ground']"))
            self.assertIsNotNone(worldbody.find("geom[@name='city_ground']"))
            self.assertIsNotNone(worldbody.find("body[@name='building']"))
            self.assertIsNotNone(worldbody.find("body[@name='vehicle']"))
            self.assertIsNotNone(composed.find("actuator"))
            self.assertIsNotNone(composed.find("contact"))

    def test_keep_robot_ground_preserves_ground(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            robot_xml = root / "robot.xml"
            world_xml = root / "world.xml"
            output = root / "out.xml"
            robot_xml.write_text(
                "<mujoco><worldbody><geom name='ground' type='plane' size='1 1 .1'/><body name='robot'/></worldbody></mujoco>",
                encoding="utf-8",
            )
            world_xml.write_text(
                "<mujoco><worldbody><geom name='world_ground' type='plane' size='1 1 .1'/></worldbody></mujoco>",
                encoding="utf-8",
            )

            receipt = COMPOSE.compose_mujoco_world(
                robot_xml, world_xml, output, keep_robot_ground=True
            )

            self.assertEqual(receipt["removed_robot_ground_geoms"], 0)
            tree = ET.parse(output)
            self.assertIsNotNone(tree.find("./worldbody/geom[@name='ground']"))

    def test_duplicate_named_objects_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            robot_xml = root / "robot.xml"
            world_xml = root / "world.xml"
            output = root / "out.xml"
            robot_xml.write_text(
                "<mujoco><worldbody><body name='shared'/></worldbody></mujoco>",
                encoding="utf-8",
            )
            world_xml.write_text(
                "<mujoco><worldbody><body name='shared'/></worldbody></mujoco>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(COMPOSE.ComposeError, "object collision"):
                COMPOSE.compose_mujoco_world(robot_xml, world_xml, output)

    def test_freejoint_and_joint_names_share_collision_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            robot_xml = root / "robot.xml"
            world_xml = root / "world.xml"
            output = root / "out.xml"
            robot_xml.write_text(
                "<mujoco><worldbody><body name='robot'><freejoint name='shared_joint'/></body></worldbody></mujoco>",
                encoding="utf-8",
            )
            world_xml.write_text(
                "<mujoco><worldbody><body name='world_body'><joint name='shared_joint' type='hinge'/></body></worldbody></mujoco>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(COMPOSE.ComposeError, "shared_joint"):
                COMPOSE.compose_mujoco_world(robot_xml, world_xml, output)

    def test_world_runtime_sections_are_rejected_instead_of_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            robot_xml = root / "robot.xml"
            world_xml = root / "world.xml"
            output = root / "out.xml"
            robot_xml.write_text(
                "<mujoco><worldbody><body name='robot'/></worldbody></mujoco>",
                encoding="utf-8",
            )
            world_xml.write_text(
                "<mujoco><worldbody><body name='building'/></worldbody><sensor><framepos name='probe' objtype='body' objname='building'/></sensor></mujoco>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(COMPOSE.ComposeError, "unsupported top-level"):
                COMPOSE.compose_mujoco_world(robot_xml, world_xml, output)

    def test_output_cannot_overwrite_an_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            robot_xml = root / "robot.xml"
            world_xml = root / "world.xml"
            robot_xml.write_text(
                "<mujoco><worldbody><body name='robot'/></worldbody></mujoco>",
                encoding="utf-8",
            )
            world_xml.write_text(
                "<mujoco><worldbody><body name='building'/></worldbody></mujoco>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(COMPOSE.ComposeError, "output must differ"):
                COMPOSE.compose_mujoco_world(robot_xml, world_xml, robot_xml)


if __name__ == "__main__":
    unittest.main()
