#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

from path_utils import default_generated_file


DEFAULT_WORLD_NAME = "mbody_minimal_world"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compose a MuJoCo world from an MBody-generated robot MJCF."
    )
    parser.add_argument("robot_mjcf", help="MBody-generated robot MJCF")
    parser.add_argument("world_config", help="World composition YAML")
    parser.add_argument(
        "-o",
        "--output",
        help="Output world XML path. Defaults to bodies/{robot}/generated/{stem}.world.xml",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def require_child(root: ET.Element, tag: str, source: Path) -> ET.Element:
    child = root.find(tag)
    if child is None:
        raise ValueError(f"{source} does not contain <{tag}>")
    return child


def append_attrs(parent: ET.Element, tag: str, attrs: dict | None) -> ET.Element:
    normalized = {
        str(key): str(value).lower() if isinstance(value, bool) else str(value)
        for key, value in (attrs or {}).items()
    }
    return ET.SubElement(parent, tag, normalized)


def normalize_mesh_paths(asset: ET.Element, robot_mjcf_path: Path, output_path: Path) -> None:
    source_dir = robot_mjcf_path.parent
    output_dir = output_path.parent

    for mesh in asset.findall("mesh"):
        mesh_file = mesh.get("file")
        if not mesh_file:
            continue
        mesh_path = Path(mesh_file)
        if not mesh_path.is_absolute():
            mesh_path = (source_dir / mesh_path).resolve()
        mesh.set("file", os.path.relpath(mesh_path, output_dir))


def add_freejoint_if_missing(body: ET.Element) -> None:
    for child in body:
        if child.tag == "freejoint":
            return
        if child.tag == "joint" and child.get("type") == "free":
            return
    body.insert(0, ET.Element("freejoint"))


def append_configured_elements(parent: ET.Element, tag: str, values: list[dict] | None) -> None:
    for attrs in values or []:
        if not isinstance(attrs, dict):
            raise ValueError(f"{tag} entries must be YAML mappings")
        append_attrs(parent, tag, attrs)


def build_world(
    robot_root: ET.Element,
    robot_mjcf_path: Path,
    output_path: Path,
    config: dict,
) -> ET.ElementTree:
    world_root = ET.Element("mujoco", {"model": str(config.get("name", DEFAULT_WORLD_NAME))})

    compiler = robot_root.find("compiler")
    world_root.append(copy.deepcopy(compiler) if compiler is not None else ET.Element("compiler", {"angle": "radian"}))

    append_attrs(
        world_root,
        "option",
        config.get(
            "option",
            {"timestep": "0.001", "gravity": "0 0 -9.81", "integrator": "implicit"},
        ),
    )

    visual_cfg = config.get("visual", {})
    if visual_cfg:
        visual = ET.SubElement(world_root, "visual")
        for tag, attrs in visual_cfg.items():
            append_attrs(visual, tag, attrs)

    asset = ET.SubElement(world_root, "asset")
    append_configured_elements(asset, "texture", config.get("textures"))
    append_configured_elements(asset, "material", config.get("materials"))

    robot_asset = robot_root.find("asset")
    if robot_asset is not None:
        robot_asset_copy = copy.deepcopy(robot_asset)
        normalize_mesh_paths(robot_asset_copy, robot_mjcf_path, output_path)
        for child in robot_asset_copy:
            asset.append(child)

    worldbody = ET.SubElement(world_root, "worldbody")
    append_configured_elements(worldbody, "geom", config.get("world_geoms"))
    append_configured_elements(worldbody, "light", config.get("lights"))
    append_configured_elements(worldbody, "camera", config.get("cameras"))

    robot_cfg = config.get("robot", {})
    if not isinstance(robot_cfg, dict):
        raise ValueError("robot config must be a YAML mapping")
    start_pos = str(robot_cfg.get("pos", "0 0 0"))
    add_freejoint = bool(robot_cfg.get("add_freejoint", True))

    robot_worldbody = require_child(robot_root, "worldbody", robot_mjcf_path)
    robot_bodies = [copy.deepcopy(child) for child in robot_worldbody if child.tag == "body"]
    if not robot_bodies:
        raise ValueError(f"{robot_mjcf_path} does not contain top-level robot bodies")

    for body in robot_bodies:
        body.set("pos", start_pos)
        if add_freejoint:
            add_freejoint_if_missing(body)
        worldbody.append(body)

    if bool(config.get("copy_actuators", True)):
        robot_actuator = robot_root.find("actuator")
        if robot_actuator is not None and len(robot_actuator):
            world_root.append(copy.deepcopy(robot_actuator))

    return ET.ElementTree(world_root)


def main() -> None:
    args = parse_args()
    robot_mjcf_path = Path(args.robot_mjcf).resolve()
    world_config_path = Path(args.world_config).resolve()
    output_path = Path(args.output).resolve() if args.output else default_generated_file(robot_mjcf_path, ".world.xml")

    config = load_yaml(world_config_path)
    robot_tree = ET.parse(robot_mjcf_path)
    world_tree = build_world(robot_tree.getroot(), robot_mjcf_path, output_path, config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(world_tree, space="  ")
    world_tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
