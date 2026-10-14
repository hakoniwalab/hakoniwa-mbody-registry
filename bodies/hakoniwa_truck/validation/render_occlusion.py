#!/usr/bin/env python3
"""Render the Car 2 driver-eye view from 20 m behind the truck."""

from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
from PIL import Image

BODY = Path(__file__).resolve().parents[1]
SOURCE = BODY / "generated/model.minimal_world.xml"
OUTPUT = BODY / "validation/results/rear-occlusion.png"


def main():
    root = ET.parse(SOURCE).getroot()
    world = root.find("worldbody")
    ET.SubElement(world, "camera", {
        "name": "car2-eye-20m-behind", "mode": "fixed", "pos": "-24 0 1.15",
        "xyaxes": "0 -1 0 0 0 1", "fovy": "72",
    })
    # A conspicuous road hazard is deliberately placed ahead of the truck. It
    # should not be visible from the following car's eye point.
    ET.SubElement(world, "geom", {
        "name": "hidden_hazard", "type": "box", "pos": "8 0 0.18",
        "size": "0.8 0.8 0.18", "rgba": "1 0.15 0.02 1",
    })
    model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    renderer = mujoco.Renderer(model, height=360, width=640)
    renderer.update_scene(data, camera="car2-eye-20m-behind")
    pixels = renderer.render()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(OUTPUT)
    renderer.close()
    print(OUTPUT)


if __name__ == "__main__":
    main()
