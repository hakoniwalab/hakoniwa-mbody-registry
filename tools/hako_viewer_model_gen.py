#!/usr/bin/env python3
"""
hako_viewer_model_gen.py

Generate a minimal Hakoniwa Viewer Model JSON from:
  - viewer.recipe.yaml
  - MJCF XML

v0.1 scope:
  - base
  - movable_parts from MJCF joints
  - GLB assets by body name
  - ROS coordinate output
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required. Install with: pip install pyyaml"
    ) from exc


Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]  # MJCF order: w, x, y, z


def parse_vec3(value: Optional[str], default: Vec3 = (0.0, 0.0, 0.0)) -> Vec3:
    if not value:
        return default
    parts = [float(x) for x in value.split()]
    if len(parts) != 3:
        raise ValueError(f"Expected vec3, got: {value}")
    return (parts[0], parts[1], parts[2])


def parse_quat(value: Optional[str], default: Quat = (1.0, 0.0, 0.0, 0.0)) -> Quat:
    if not value:
        return default
    parts = [float(x) for x in value.split()]
    if len(parts) != 4:
        raise ValueError(f"Expected quat w x y z, got: {value}")
    return (parts[0], parts[1], parts[2], parts[3])


def quat_to_rpy(q: Quat) -> Vec3:
    """
    Convert quaternion in MJCF order (w, x, y, z) to roll/pitch/yaw radians.
    This is mainly for human-readable viewer model output.
    """
    w, x, y, z = q

    # roll: x-axis rotation
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # pitch: y-axis rotation
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    # yaw: z-axis rotation
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return (roll, pitch, yaw)


def round_float(v: float) -> float:
    # Stable enough for generated files, while preserving useful precision.
    return 0.0 if abs(v) < 1e-12 else round(v, 6)


def round_vec(values: Tuple[float, ...]) -> List[float]:
    return [round_float(v) for v in values]


@dataclass
class BodyInfo:
    name: str
    parent: Optional[str]
    pos: Vec3 = (0.0, 0.0, 0.0)
    quat: Quat = (1.0, 0.0, 0.0, 0.0)
    mesh_names: List[str] = field(default_factory=list)


@dataclass
class JointInfo:
    name: str
    body: str
    joint_type: str
    axis: Vec3
    pos: Vec3


class MjcfIndex:
    def __init__(self, mjcf_path: Path) -> None:
        self.mjcf_path = mjcf_path
        self.bodies: Dict[str, BodyInfo] = {}
        self.joints: Dict[str, JointInfo] = {}
        self.root = ET.parse(mjcf_path).getroot()
        self._index()

    def _index(self) -> None:
        worldbody = self.root.find("worldbody")
        if worldbody is None:
            raise ValueError("MJCF has no <worldbody>")

        for body_elem in worldbody.findall("body"):
            self._walk_body(body_elem, parent=None)

    def _walk_body(self, elem: ET.Element, parent: Optional[str]) -> None:
        name = elem.get("name")
        if not name:
            raise ValueError("All <body> elements must have a name for viewer model generation")

        body = BodyInfo(
            name=name,
            parent=parent,
            pos=parse_vec3(elem.get("pos")),
            quat=parse_quat(elem.get("quat")),
            mesh_names=[],
        )

        for geom in elem.findall("geom"):
            mesh_name = geom.get("mesh")
            if mesh_name:
                body.mesh_names.append(mesh_name)

        self.bodies[name] = body

        for joint in elem.findall("joint"):
            joint_name = joint.get("name")
            if not joint_name:
                continue
            mjcf_type = joint.get("type", "hinge")
            axis = parse_vec3(joint.get("axis"), default=(0.0, 0.0, 1.0))
            pos = parse_vec3(joint.get("pos"), default=(0.0, 0.0, 0.0))
            self.joints[joint_name] = JointInfo(
                name=joint_name,
                body=name,
                joint_type=mjcf_type,
                axis=axis,
                pos=pos,
            )

        for child in elem.findall("body"):
            self._walk_body(child, parent=name)

    def get_body(self, name: str) -> BodyInfo:
        try:
            return self.bodies[name]
        except KeyError as exc:
            raise KeyError(f"Body not found in MJCF: {name}") from exc

    def get_joint(self, name: str) -> JointInfo:
        try:
            return self.joints[name]
        except KeyError as exc:
            raise KeyError(f"Joint not found in MJCF: {name}") from exc


def resolve_path(path_value: str, base_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def motion_type_from_joint(joint: JointInfo) -> str:
    # MJCF hinge can be revolute or continuous depending on range/limited.
    # v0.1 treats hinge as continuous for viewer animation unless later extended.
    if joint.joint_type == "slide":
        return "prismatic"
    if joint.joint_type == "hinge":
        return "continuous"
    return joint.joint_type


def make_asset_id(body_name: str) -> str:
    return body_name


def make_asset_path(glb_dir: str, body_name: str) -> str:
    return f"{glb_dir.rstrip('/')}/{body_name}.glb"


def has_visual_asset(body: BodyInfo) -> bool:
    # For body_name mapping, the generated GLB is expected per body if that body has any mesh geom.
    return bool(body.mesh_names)


def build_viewer_model(recipe: Dict[str, Any], recipe_path: Path) -> Dict[str, Any]:
    recipe_dir = recipe_path.parent
    mjcf_path = resolve_path(recipe["mjcf"], recipe_dir)
    index = MjcfIndex(mjcf_path)

    robot_name = recipe.get("robot") or index.root.get("model") or mjcf_path.stem
    base_name = recipe["base"]
    base_body = index.get_body(base_name)

    assets_cfg = recipe.get("assets", {})
    glb_dir = assets_cfg.get("glb_dir", "parts")
    asset_map = assets_cfg.get("map", "body_name")
    if asset_map != "body_name":
        raise ValueError(f"Unsupported assets.map for v0.1: {asset_map}")

    # Include all MJCF bodies that have mesh geoms.
    assets = []
    for body_name in index.bodies:
        body = index.bodies[body_name]
        if has_visual_asset(body):
            assets.append({
                "id": make_asset_id(body_name),
                "type": "glb",
                "path": make_asset_path(glb_dir, body_name),
            })

    movable_joint_names = recipe.get("movable_joints", recipe.get("movables", []))
    movable_parts = []
    for joint_name in movable_joint_names:
        joint = index.get_joint(joint_name)
        body = index.get_body(joint.body)

        movable_parts.append({
            "name": body.name,
            "joint": joint.name,
            "parent": body.parent,
            "asset": make_asset_id(body.name),
            "mount": {
                "xyz": round_vec(body.pos),
                "rpy": round_vec(quat_to_rpy(body.quat)),
            },
            "motion": {
                "type": motion_type_from_joint(joint),
                "axis": round_vec(joint.axis),
            },
        })

    fixed_body_names = recipe.get("fixed_bodies", [])
    fixed_parts = []
    for body_name in fixed_body_names:
        body = index.get_body(body_name)
        fixed_parts.append({
            "name": body.name,
            "parent": body.parent,
            "asset": make_asset_id(body.name),
            "mount": {
                "xyz": round_vec(body.pos),
                "rpy": round_vec(quat_to_rpy(body.quat)),
            },
        })

    model: Dict[str, Any] = {
        "format": "hako_viewer_model",
        "version": str(recipe.get("version", "0.1")),
        "coordinate_system": recipe.get("coordinate_system", recipe.get("coordinate", "ros")),
        "robot": {
            "name": robot_name,
            "root": base_name,
        },
        "assets": assets,
        "base": {
            "name": base_name,
            "asset": make_asset_id(base_name),
            "mount": {
                # The chosen base is the viewer root, so its local mount is identity.
                "xyz": [0.0, 0.0, 0.0],
                "rpy": [0.0, 0.0, 0.0],
            },
        },
        "movable_parts": movable_parts,
    }

    if fixed_parts:
        model["fixed_parts"] = fixed_parts

    return model


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Hakoniwa Viewer Model JSON from viewer.recipe.yaml and MJCF."
    )
    parser.add_argument("recipe", type=Path, help="Path to viewer.recipe.yaml")
    parser.add_argument("-o", "--out", type=Path, default=None, help="Output JSON path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON with indent=2")
    args = parser.parse_args()

    recipe_path = args.recipe.resolve()
    with recipe_path.open("r", encoding="utf-8") as f:
        recipe = yaml.safe_load(f)

    model = build_viewer_model(recipe, recipe_path)

    text = json.dumps(model, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
