#!/usr/bin/env python3
"""Render repeatable appearance evidence for Car 2 and the box truck."""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
RESULTS = Path(__file__).resolve().parent / "results"


def render(model_path: Path, *, azimuth: float, elevation: float, distance: float,
           lookat: tuple[float, float, float], width: int = 640, height: int = 420) -> Image.Image:
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = lookat
    camera.distance = distance
    camera.azimuth = azimuth
    camera.elevation = elevation
    renderer = mujoco.Renderer(model, height=height, width=width)
    renderer.update_scene(data, camera=camera)
    image = Image.fromarray(renderer.render())
    renderer.close()
    return image


def render_driver_eye(
    model_path: Path,
    width: int = 640,
    height: int = 360,
    hidden_geom_prefixes: tuple[str, ...] = (),
    joint_positions: dict[str, float] | None = None,
    display_body_angles: dict[str, float] | None = None,
) -> Image.Image:
    """Render from Urban Mobility's vehicle-local driver eye toward +x."""
    root = ET.parse(model_path).getroot()
    # from_xml_string has no source-directory context; preserve relative asset
    # semantics by resolving file references before compiling the temporary view.
    for asset in root.findall("./asset/*[@file]"):
        path = Path(asset.get("file", ""))
        if not path.is_absolute():
            asset.set("file", str((model_path.parent / path).resolve()))
    vehicle = root.find(".//body[@name='vehicle']")
    if vehicle is None:
        raise RuntimeError("vehicle body not found")
    for geom in list(vehicle.findall("./geom")):
        name = geom.get("name", "")
        if name.startswith(hidden_geom_prefixes):
            vehicle.remove(geom)
    for body_name, angle in (display_body_angles or {}).items():
        body = root.find(f".//body[@name='{body_name}']")
        if body is None:
            raise RuntimeError(f"display body not found: {body_name}")
        base_euler = [float(value) for value in body.get("euler", "0 0 0").split()]
        if len(base_euler) != 3:
            raise RuntimeError(f"display body has invalid euler: {body_name}")
        # The Three.js viewer applies display motion about the body's local X
        # axis after its fixed mount transform.
        base_euler[0] += angle
        body.set("euler", " ".join(f"{value:.9g}" for value in base_euler))
    worldbody = root.find("./worldbody")
    if worldbody is None:
        raise RuntimeError("worldbody not found")
    for distance, color in ((5, "1 0.15 0.05 1"), (10, "1 0.8 0.05 1"), (20, "0.1 0.45 1 1")):
        ET.SubElement(worldbody, "geom", {
            "name": f"driver_sightline_{distance}m",
            "type": "box",
            "pos": f"{distance} -0.38 0.4",
            "size": "0.08 0.08 0.4",
            "rgba": color,
            "contype": "0",
            "conaffinity": "0",
        })
    ET.SubElement(vehicle, "camera", {
        "name": "driver_eye_validation",
        "pos": "-0.05 -0.38 0.84",
        # camera -Z looks forward (+vehicle X), camera +Y is world up.
        "xyaxes": "0 -1 0 0 0 1",
        "fovy": "72",
    })
    model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    data = mujoco.MjData(model)
    for joint_name, value in (joint_positions or {}).items():
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            raise RuntimeError(f"joint not found: {joint_name}")
        data.qpos[model.jnt_qposadr[joint_id]] = value
    mujoco.mj_forward(model, data)
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FIXED
    camera.fixedcamid = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_CAMERA, "driver_eye_validation"
    )
    renderer = mujoco.Renderer(model, height=height, width=width)
    renderer.update_scene(data, camera=camera)
    image = Image.fromarray(renderer.render())
    renderer.close()
    return image


def labelled(image: Image.Image, label: str) -> Image.Image:
    result = Image.new("RGB", (image.width, image.height + 32), "white")
    result.paste(image, (0, 32))
    ImageDraw.Draw(result).text((12, 9), label, fill="black")
    return result


def montage(images: list[tuple[str, Image.Image]]) -> Image.Image:
    tiles = [labelled(image, label) for label, image in images]
    result = Image.new("RGB", (tiles[0].width * 2, tiles[0].height * 2), "white")
    for index, tile in enumerate(tiles):
        result.paste(tile, ((index % 2) * tile.width, (index // 2) * tile.height))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="Filename label, normally before or after")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)

    car = ROOT / "bodies/hakoniwa_car2/generated"
    variants = [
        ("graphite", car / "model.minimal_world.xml"),
        ("white", car / "model-white.minimal_world.xml"),
        ("red", car / "model-red.minimal_world.xml"),
        ("blue", car / "model-blue.minimal_world.xml"),
    ]
    car_images = [
        (name, render(path, azimuth=135, elevation=-18, distance=7.0, lookat=(0, 0, 0.55)))
        for name, path in variants
    ]
    montage(car_images).save(RESULTS / f"car2-{args.label}-oblique.png")
    car_side_images = [
        (name, render(path, azimuth=90, elevation=-8, distance=6.4, lookat=(0, 0, 0.55)))
        for name, path in variants
    ]
    montage(car_side_images).save(RESULTS / f"car2-{args.label}-side.png")
    car_rear_images = [
        (name, render(path, azimuth=45, elevation=-18, distance=7.0, lookat=(0, 0, 0.55)))
        for name, path in variants
    ]
    montage(car_rear_images).save(RESULTS / f"car2-{args.label}-rear-oblique.png")
    render_driver_eye(variants[0][1]).save(
        RESULTS / f"car2-{args.label}-driver-eye-straight.png"
    )
    left_steer_rad = 0.25
    render_driver_eye(
        variants[0][1],
        joint_positions={
            "front_left_steer_joint": left_steer_rad,
        },
        display_body_angles={"steering_wheel": left_steer_rad * 15.0},
    ).save(RESULTS / f"car2-{args.label}-driver-eye-left.png")

    truck = ROOT / "bodies/hakoniwa_truck/generated/model.minimal_world.xml"
    truck_result = ROOT / "bodies/hakoniwa_truck/validation/results"
    truck_result.mkdir(parents=True, exist_ok=True)
    render(truck, azimuth=135, elevation=-16, distance=12.5, lookat=(0, 0, 1.25)).save(
        truck_result / f"truck-{args.label}-oblique.png"
    )
    print(RESULTS / f"car2-{args.label}-oblique.png")
    print(RESULTS / f"car2-{args.label}-side.png")
    print(RESULTS / f"car2-{args.label}-rear-oblique.png")
    print(RESULTS / f"car2-{args.label}-driver-eye-straight.png")
    print(RESULTS / f"car2-{args.label}-driver-eye-left.png")
    print(truck_result / f"truck-{args.label}-oblique.png")


if __name__ == "__main__":
    main()
