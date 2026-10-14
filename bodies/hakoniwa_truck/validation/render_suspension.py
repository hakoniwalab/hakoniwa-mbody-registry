#!/usr/bin/env python3
"""Render a repeatable side view of the truck suspension ride height."""

from pathlib import Path

import mujoco
from PIL import Image


HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / "generated/model.minimal_world.xml"
OUTPUT = HERE / "results/truck-suspension-side.png"


def main() -> None:
    model = mujoco.MjModel.from_xml_path(str(MODEL))
    data = mujoco.MjData(model)
    # Let the suspension settle under the empty-box sprung mass.
    for _ in range(int(2.0 / model.opt.timestep)):
        mujoco.mj_step(model, data)
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = (0.0, 0.0, 1.35)
    camera.distance = 10.5
    camera.azimuth = 90
    camera.elevation = -5
    # Keep this within the model's default 640x480 offscreen framebuffer so
    # the evidence renderer works without changing the product MJCF.
    renderer = mujoco.Renderer(model, height=360, width=640)
    renderer.update_scene(data, camera=camera)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(renderer.render()).save(OUTPUT)
    renderer.close()
    print(OUTPUT)


if __name__ == "__main__":
    main()
