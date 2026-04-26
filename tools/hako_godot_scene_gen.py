#!/usr/bin/env python3
"""
hako_godot_scene_gen.py

Generate a minimal Godot .tscn scene from Hakoniwa Viewer Model JSON.

v0.1 scope:
  - Node3D scene
  - GLB PackedScene ext_resources
  - RosToGodot fixed coordinate conversion node
  - Visuals node as robot pose target
  - base node
  - movable_parts nodes
  - fixed_parts nodes
  - optional fallback nodes for unused visual assets
  - optional sync script resource

Expected input:
  hako_viewer_model.json

Expected output:
  TurtleBot3.generated.tscn
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def sanitize_resource_id(value: str) -> str:
    # Godot ext_resource id strings can be descriptive.
    # Keep them short, deterministic, and safe.
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", value)
    if not safe:
        safe = "res"
    if safe[0].isdigit():
        safe = "_" + safe
    return safe


def node_name(value: str) -> str:
    # Godot node names can be flexible, but keep generated names stable.
    return value.replace("/", "_")


def to_godot_res_path(path: str, res_root: str) -> str:
    # Viewer model paths are usually relative such as parts/base_link.glb.
    # Godot wants res://...
    if path.startswith("res://"):
        return path

    if res_root == "res://":
        return "res://" + path.lstrip("/")

    return res_root.rstrip("/") + "/" + path.lstrip("/")


def vec3(values: List[float]) -> str:
    x, y, z = values
    return f"Vector3({fmt(x)}, {fmt(y)}, {fmt(z)})"


def fmt(value: float) -> str:
    # Pretty, stable Godot numeric output.
    value = 0.0 if abs(float(value)) < 1e-12 else float(value)
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    if text == "":
        return "0"
    return text


def transform_ros_to_godot_line() -> str:
    # This is the version validated in Godot during manual reference testing.
    #
    # Desired vector mapping:
    #   godot_x = -ros_y
    #   godot_y =  ros_z
    #   godot_z = -ros_x
    #
    # Godot .tscn Transform3D serialization order is basis x, y, z, then origin.
    return "Transform3D(0, -1, 0, 0, 0, 1, -1, 0, 0, 0, 0, 0)"


def load_model(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        model = json.load(f)

    if model.get("format") != "hako_viewer_model":
        fail(f"Unsupported model format: {model.get('format')}")
    return model


def build_asset_map(model: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    assets = {}
    for asset in model.get("assets", []):
        asset_id = asset.get("id")
        if not asset_id:
            fail("Asset without id")
        if asset.get("type") != "glb":
            fail(f"Unsupported asset type for '{asset_id}': {asset.get('type')}")
        assets[asset_id] = asset
    return assets


def emit_header(lines: List[str], load_steps: int) -> None:
    lines.append(f"[gd_scene load_steps={load_steps} format=3]")
    lines.append("")


def emit_ext_resources(
    lines: List[str],
    model: Dict[str, Any],
    asset_map: Dict[str, Dict[str, Any]],
    res_root: str,
    sync_script: Optional[str],
) -> Dict[str, str]:
    resource_ids: Dict[str, str] = {}

    counter = 1
    for asset in model.get("assets", []):
        asset_id = asset["id"]
        rid = f"{counter}_{sanitize_resource_id(asset_id)}"
        resource_ids[asset_id] = rid
        path = to_godot_res_path(asset["path"], res_root)
        lines.append(f'[ext_resource type="PackedScene" path="{path}" id="{rid}"]')
        counter += 1

    if sync_script:
        rid = f"{counter}_sync"
        resource_ids["__sync_script__"] = rid
        # Use only the filename of the sync script for the Godot resource path.
        script_filename = Path(sync_script).name
        path = to_godot_res_path(script_filename, res_root)
        lines.append(f'[ext_resource type="Script" path="{path}" id="{rid}"]')

    lines.append("")
    return resource_ids


def emit_node(
    lines: List[str],
    name: str,
    typ: str,
    parent: Optional[str] = None,
    instance: Optional[str] = None,
) -> None:
    attrs = [f'name="{name}"']
    if typ:
        attrs.append(f'type="{typ}"')
    if parent is not None:
        attrs.append(f'parent="{parent}"')
    if instance is not None:
        attrs.append(f'instance=ExtResource("{instance}")')
    lines.append("[node " + " ".join(attrs) + "]")


def emit_transform(lines: List[str], mount: Dict[str, Any]) -> None:
    xyz = mount.get("xyz", [0.0, 0.0, 0.0])
    rpy = mount.get("rpy", [0.0, 0.0, 0.0])
    lines.append(f"position = {vec3(xyz)}")
    lines.append(f"rotation = {vec3(rpy)}")


def emit_model_instance(
    lines: List[str],
    parent_path: str,
    asset_id: str,
    resource_ids: Dict[str, str],
) -> None:
    rid = resource_ids.get(asset_id)
    if rid is None:
        # Some bodies may have no visual asset. Skip silently for v0.1.
        return
    emit_node(lines, "model", "", parent=parent_path, instance=rid)
    lines.append("")


def emit_part_node(
    lines: List[str],
    part: Dict[str, Any],
    parent_path: str,
    resource_ids: Dict[str, str],
) -> str:
    """
    Emit one viewer-model part node and its optional visual model child.

    Returns the generated Godot NodePath for the part body.
    """
    part_name = node_name(part["name"])
    part_path = f"{parent_path}/{part_name}"

    emit_node(lines, part_name, "Node3D", parent=parent_path)
    emit_transform(lines, part.get("mount", {"xyz": [0, 0, 0], "rpy": [0, 0, 0]}))
    lines.append("")
    emit_model_instance(lines, part_path, part.get("asset", part["name"]), resource_ids)

    return part_path


def emit_parts_with_parent_resolution(
    *,
    lines: List[str],
    parts: List[Dict[str, Any]],
    section_name: str,
    base_body_name: str,
    node_paths: Dict[str, str],
    used_asset_ids: Set[str],
    used_body_names: Set[str],
    resource_ids: Dict[str, str],
) -> None:
    """
    Emit movable_parts or fixed_parts in an order that respects parent-body dependencies.

    v0.1 does not auto-create intermediate MJCF bodies. If a part's parent was not
    generated by base/movable_parts/fixed_parts, generation fails with a clear error.
    """
    pending = list(parts)

    while pending:
        progressed = False
        remaining: List[Dict[str, Any]] = []

        for part in pending:
            part_body = part.get("name")
            if not part_body:
                fail(f"{section_name} entry without name")

            parent_body = part.get("parent") or base_body_name
            if parent_body not in node_paths:
                remaining.append(part)
                continue

            parent_path = node_paths[parent_body]
            part_path = emit_part_node(lines, part, parent_path, resource_ids)

            node_paths[part_body] = part_path
            used_body_names.add(part_body)
            if part.get("asset"):
                used_asset_ids.add(part["asset"])

            progressed = True

        if not remaining:
            return

        if not progressed:
            details = []
            known = ", ".join(sorted(node_paths.keys()))
            for part in remaining:
                details.append(
                    f"{part.get('name', '<unnamed>')} -> parent {part.get('parent') or base_body_name}"
                )
            fail(
                f"Could not resolve parent nodes for {section_name}: "
                f"{', '.join(details)}. Generated bodies: {known}"
            )

        pending = remaining


def build_scene(
    model: Dict[str, Any],
    scene_name: Optional[str],
    res_root: str,
    sync_script: Optional[str],
    include_unused_assets_as_fixed: bool,
) -> str:
    asset_map = build_asset_map(model)

    robot = model.get("robot", {})
    root_name = node_name(scene_name or robot.get("name", "HakoniwaRobot"))

    # load_steps = 1 implicit scene + ext_resources count.
    ext_count = len(model.get("assets", [])) + (1 if sync_script else 0)
    load_steps = ext_count + 1

    lines: List[str] = []
    emit_header(lines, load_steps)
    resource_ids = emit_ext_resources(lines, model, asset_map, res_root, sync_script)

    emit_node(lines, root_name, "Node3D")
    lines.append("")

    emit_node(lines, "HakoSync", "Node", parent=".")
    if sync_script:
        lines.append(f'script = ExtResource("{resource_ids["__sync_script__"]}")')
    lines.append("")

    lines.append("; Fixed ROS -> Godot coordinate conversion wrapper.")
    lines.append("; ROS:   X forward, Y left, Z up")
    lines.append("; Godot: X right,   Y up,   -Z forward")
    lines.append("; Mapping: godot_x = -ros_y, godot_y = ros_z, godot_z = -ros_x")
    emit_node(lines, "RosToGodot", "Node3D", parent=".")
    lines.append(f"transform = {transform_ros_to_godot_line()}")
    lines.append("")

    emit_node(lines, "Visuals", "Node3D", parent="RosToGodot")
    lines.append("")

    # Base node.
    base = model.get("base")
    if not base:
        fail("Viewer model has no base")
    if not base.get("name"):
        fail("Viewer model base has no name")

    base_body_name = base["name"]
    base_name = node_name(base_body_name)
    base_path = f"RosToGodot/Visuals/{base_name}"

    emit_node(lines, base_name, "Node3D", parent="RosToGodot/Visuals")
    emit_transform(lines, base.get("mount", {"xyz": [0, 0, 0], "rpy": [0, 0, 0]}))
    lines.append("")
    emit_model_instance(lines, base_path, base.get("asset", base_body_name), resource_ids)

    node_paths: Dict[str, str] = {base_body_name: base_path}
    used_asset_ids: Set[str] = set()
    used_body_names: Set[str] = {base_body_name}
    if base.get("asset"):
        used_asset_ids.add(base["asset"])

    # Movable parts are generated using body-name parent resolution.
    emit_parts_with_parent_resolution(
        lines=lines,
        parts=model.get("movable_parts", []),
        section_name="movable_parts",
        base_body_name=base_body_name,
        node_paths=node_paths,
        used_asset_ids=used_asset_ids,
        used_body_names=used_body_names,
        resource_ids=resource_ids,
    )

    # Fixed parts are first-class viewer nodes for non-moving visual bodies.
    emit_parts_with_parent_resolution(
        lines=lines,
        parts=model.get("fixed_parts", []),
        section_name="fixed_parts",
        base_body_name=base_body_name,
        node_paths=node_paths,
        used_asset_ids=used_asset_ids,
        used_body_names=used_body_names,
        resource_ids=resource_ids,
    )

    # Fallback / debug convenience:
    # Attach visual assets that are not referenced by base/movable_parts/fixed_parts
    # under the base body with identity transform. This helps detect missing model
    # entries while keeping the generated scene inspectable. Use --no-unused-assets
    # to disable this behavior.
    if include_unused_assets_as_fixed:
        for asset in model.get("assets", []):
            asset_id = asset["id"]
            if asset_id in used_asset_ids:
                continue
            fixed_name = node_name(asset_id)
            emit_node(lines, fixed_name, "Node3D", parent=base_path)
            lines.append("position = Vector3(0, 0, 0)")
            lines.append("rotation = Vector3(0, 0, 0)")
            lines.append("")
            emit_model_instance(lines, f"{base_path}/{fixed_name}", asset_id, resource_ids)

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Godot .tscn scene from hako_viewer_model.json"
    )
    parser.add_argument("model", type=Path, help="Path to hako_viewer_model.json")
    parser.add_argument("-o", "--out", type=Path, required=True, help="Output .tscn path")
    parser.add_argument("--scene-name", default=None, help="Root node name. Defaults to robot.name")
    parser.add_argument("--res-root", default="res://", help="Godot resource root prefix. Default: res://")
    parser.add_argument("--sync-script", default=None, help="Optional sync script path, e.g. tb3_reference_sync.gd")
    parser.add_argument(
        "--no-unused-assets",
        action="store_true",
        help="Do not attach assets that are not referenced by base/movable_parts/fixed_parts",
    )
    args = parser.parse_args()

    model = load_model(args.model)
    scene = build_scene(
        model=model,
        scene_name=args.scene_name,
        res_root=args.res_root,
        sync_script=args.sync_script,
        include_unused_assets_as_fixed=not args.no_unused_assets,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(scene, encoding="utf-8")
    print(f"Successfully wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
