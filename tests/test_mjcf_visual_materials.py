import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/mjcf_apply_visual_materials.py"
SPEC = importlib.util.spec_from_file_location("mjcf_apply_visual_materials", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VISUALS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VISUALS)


class VisualMaterialsTest(unittest.TestCase):
    def test_materials_are_added_and_assigned_by_mesh_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.xml"
            config = root / "visuals.yaml"
            output = root / "output.xml"
            source.write_text(
                '<mujoco><asset><mesh name="body_mesh" file="body.obj"/></asset>'
                '<worldbody><body><geom mesh="body_mesh" rgba="1 0 0 1"/></body>'
                '</worldbody></mujoco>',
                encoding="utf-8",
            )
            config.write_text(
                'materials:\n  body: {rgba: "0.3 0.4 0.5 1", specular: 0.2}\n'
                'mesh_assignments:\n  body_mesh: body\n',
                encoding="utf-8",
            )

            VISUALS.apply_visual_materials(source, config, output)

            model = ET.parse(output).getroot()
            material = model.find("asset/material[@name='body']")
            geom = model.find(".//geom[@mesh='body_mesh']")
            self.assertIsNotNone(material)
            self.assertEqual(material.get("rgba"), "0.3 0.4 0.5 1")
            self.assertEqual(geom.get("material"), "body")
            self.assertNotIn("rgba", geom.attrib)

    def test_unknown_mesh_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.xml"
            config = root / "visuals.yaml"
            source.write_text("<mujoco><asset/></mujoco>", encoding="utf-8")
            config.write_text(
                'materials:\n  body: {rgba: "1 1 1 1"}\n'
                'mesh_assignments:\n  missing: body\n',
                encoding="utf-8",
            )
            with self.assertRaises(VISUALS.VisualMaterialError):
                VISUALS.apply_visual_materials(source, config, root / "output.xml")


if __name__ == "__main__":
    unittest.main()
