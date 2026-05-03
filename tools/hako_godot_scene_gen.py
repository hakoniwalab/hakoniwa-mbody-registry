#!/usr/bin/env python3
"""
hako_godot_scene_gen.py

Generate a Godot .tscn scene from Hakoniwa Viewer Model JSON.

v0.1 scope:
  - Robot scene hierarchy from viewer model
  - HakoSync wrapper script generation
  - Optional HakoniwaSimNode / HakoniwaCodecNode generation
  - Template-compatible asset/config paths via godot_scene.yaml
  - Minimal default material overrides for GLB visuals
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def sanitize_resource_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", value)
    if not safe:
        safe = "res"
    if safe[0].isdigit():
        safe = "_" + safe
    return safe


def node_name(value: str) -> str:
    return value.replace("/", "_")


def fmt(value: float) -> str:
    value = 0.0 if abs(float(value)) < 1e-12 else float(value)
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    if text in ("", "-0"):
        return "0"
    return text


def vec3(values: List[float]) -> str:
    x, y, z = values
    return f"Vector3({fmt(x)}, {fmt(y)}, {fmt(z)})"


def transform_ros_to_godot_line() -> str:
    return "Transform3D(0, -1, 0, 0, 0, 1, -1, 0, 0, 0, 0.16596496, 0)"


def load_model(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_obj:
        model = json.load(file_obj)
    if model.get("format") != "hako_viewer_model":
        fail(f"Unsupported model format: {model.get('format')}")
    return model


def load_scene_config(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {
            "scene": {},
            "paths": {},
            "nodes": {
                "generate_sim_node": False,
                "generate_codec_node": False,
            },
            "materials": {
                "apply_default_materials": False,
            },
        }

    with path.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)

    if not isinstance(config, dict):
        fail("godot_scene.yaml root must be a mapping.")
    if config.get("format") != "hako_godot_scene":
        fail("godot_scene.yaml 'format' must be 'hako_godot_scene'.")
    return config


def to_scene_part_path(asset_path: str, parts_dir: str) -> str:
    filename = Path(asset_path).name
    return parts_dir.rstrip("/") + "/" + filename


def build_asset_map(model: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    assets: Dict[str, Dict[str, Any]] = {}
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


def emit_template_environment(lines: List[str]) -> None:
    lines.append('[sub_resource type="ProceduralSkyMaterial" id="ProceduralSkyMaterial_4pki5"]')
    lines.append("sky_top_color = Color(0.09670233, 0.15326172, 0.99999994, 1)")
    lines.append("sky_horizon_color = Color(0.6141338, 0.75738144, 0.9939726, 1)")
    lines.append("ground_bottom_color = Color(0.39721388, 0.34378844, 0.28378502, 1)")
    lines.append("ground_horizon_color = Color(0.44069412, 0.62142915, 0.9144665, 1)")
    lines.append("")
    lines.append('[sub_resource type="Sky" id="Sky_jorao"]')
    lines.append('sky_material = SubResource("ProceduralSkyMaterial_4pki5")')
    lines.append("process_mode = 1")
    lines.append("")
    lines.append('[sub_resource type="Environment" id="Environment_default"]')
    lines.append("background_mode = 2")
    lines.append('sky = SubResource("Sky_jorao")')
    lines.append("sky_custom_fov = 45.0")
    lines.append("ambient_light_source = 2")
    lines.append("ambient_light_color = Color(1, 1, 1, 1)")
    lines.append("ambient_light_energy = 0.25")
    lines.append("ssao_enabled = true")
    lines.append("ssao_radius = 0.8")
    lines.append("ssao_intensity = 0.5")
    lines.append("ssao_detail = 0.3")
    lines.append("")


def emit_default_materials(lines: List[str]) -> Dict[str, str]:
    material_defs = {
        "base_link": ("StandardMaterial3D_4pki5", "Color(0.2509804, 0.2509804, 0.2509804, 1)", "0.8"),
        "wheel_left_link": ("StandardMaterial3D_jorao", "Color(0.0627451, 0.0627451, 0.0627451, 1)", None),
        "wheel_right_link": ("StandardMaterial3D_3oxhj", "Color(0.0627451, 0.0627451, 0.0627451, 1)", None),
        "base_scan": ("StandardMaterial3D_p6uxh", "Color(0.36094868, 0.36094868, 0.36094865, 1)", None),
    }
    for _asset_id, (sub_id, color, roughness) in material_defs.items():
        lines.append(f'[sub_resource type="StandardMaterial3D" id="{sub_id}"]')
        lines.append(f"albedo_color = {color}")
        if roughness is not None:
            lines.append(f"roughness = {roughness}")
        lines.append("")
    return {asset_id: sub_id for asset_id, (sub_id, _color, _roughness) in material_defs.items()}


def emit_ground_mesh(lines: List[str]) -> None:
    lines.append('[sub_resource type="PlaneMesh" id="PlaneMesh_csd54"]')
    lines.append("size = Vector2(20, 20)")
    lines.append("")


def emit_ext_resources(
    lines: List[str],
    model: Dict[str, Any],
    scene_config: Dict[str, Any],
    sync_script_res_path: str,
    include_sim_node: bool,
    include_codec_node: bool,
) -> Dict[str, str]:
    resource_ids: Dict[str, str] = {}
    parts_dir = scene_config.get("paths", {}).get("parts_dir", "res://assets/parts")

    counter = 1
    for asset in model.get("assets", []):
        asset_id = asset["id"]
        rid = f"{counter}_{sanitize_resource_id(asset_id)}"
        resource_ids[asset_id] = rid
        path = to_scene_part_path(asset["path"], parts_dir)
        lines.append(f'[ext_resource type="PackedScene" path="{path}" id="{rid}"]')
        counter += 1

    resource_ids["__sync_script__"] = f"{counter}_sync"
    lines.append(f'[ext_resource type="Script" path="{sync_script_res_path}" id="{resource_ids["__sync_script__"]}"]')
    counter += 1

    if include_sim_node:
        resource_ids["__sim_node__"] = f"{counter}_{sanitize_resource_id('r8spy')}"
        lines.append(
            '[ext_resource type="Script" path="res://addons/hakoniwa/scripts/hakoniwa_simulation_node.gd" '
            f'id="{resource_ids["__sim_node__"]}"]'
        )
        counter += 1

    if include_codec_node:
        resource_ids["__codec_node__"] = f"{counter}_{sanitize_resource_id('4pki5')}"
        lines.append(
            '[ext_resource type="Script" path="res://addons/hakoniwa/scripts/hakoniwa_codec_node.gd" '
            f'id="{resource_ids["__codec_node__"]}"]'
        )
        counter += 1

    lines.append("")
    return resource_ids


def emit_model_instance(lines: List[str], parent_path: str, asset_id: str, resource_ids: Dict[str, str]) -> None:
    rid = resource_ids.get(asset_id)
    if rid is None:
        return
    emit_node(lines, "model", "", parent=parent_path, instance=rid)
    lines.append("")


def emit_part_node(
    lines: List[str],
    part: Dict[str, Any],
    parent_path: str,
    resource_ids: Dict[str, str],
    material_ids: Dict[str, str],
    apply_default_materials: bool,
) -> str:
    part_name = node_name(part["name"])
    part_path = f"{parent_path}/{part_name}"

    emit_node(lines, part_name, "Node3D", parent=parent_path)
    xyz = part.get("mount", {}).get("xyz", [0.0, 0.0, 0.0])
    rpy = part.get("mount", {}).get("rpy", [0.0, 0.0, 0.0])
    lines.append(f"position = {vec3(xyz)}")
    lines.append(f"rotation = {vec3(rpy)}")
    lines.append("")

    asset_id = part.get("asset", part["name"])
    emit_model_instance(lines, part_path, asset_id, resource_ids)
    if apply_default_materials and asset_id in material_ids:
        lines.append(
            f'[node name="{asset_id}_visual_0" parent="{part_path}/model/{part_name}" index="0"]'
        )
        lines.append(f'surface_material_override/0 = SubResource("{material_ids[asset_id]}")')
        lines.append("")

    return part_path


def emit_parts_with_parent_resolution(
    *,
    lines: List[str],
    parts: List[Dict[str, Any]],
    section_name: str,
    base_body_name: str,
    node_paths: Dict[str, str],
    resource_ids: Dict[str, str],
    material_ids: Dict[str, str],
    apply_default_materials: bool,
    used_asset_ids: Set[str],
) -> None:
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
            part_path = emit_part_node(
                lines=lines,
                part=part,
                parent_path=node_paths[parent_body],
                resource_ids=resource_ids,
                material_ids=material_ids,
                apply_default_materials=apply_default_materials,
            )
            node_paths[part_body] = part_path
            if part.get("asset"):
                used_asset_ids.add(part["asset"])
            progressed = True

        if not remaining:
            return
        if not progressed:
            details = ", ".join(
                f"{part.get('name', '<unnamed>')} -> parent {part.get('parent') or base_body_name}"
                for part in remaining
            )
            fail(f"Could not resolve parent nodes for {section_name}: {details}")
        pending = remaining


def default_sync_script_text(profile_path: str) -> str:
    return f'''extends "res://addons/hakoniwa_robot_sync/scripts/robot_sync_controller.gd"


func _ready() -> void:
\tvar sim_node := get_node_or_null("../HakoniwaSimNode")
\tif sim_node_path.is_empty() and sim_node != null:
\t\tsim_node_path = sim_node.get_path()
\tif target_root_path.is_empty():
\t\ttarget_root_path = $"../RosToGodot".get_path()
\tif profile_path.is_empty():
\t\tprofile_path = "{profile_path}"
\tsuper._ready()
'''


def write_sync_script(output_scene: Path, sync_script_name: str, profile_path: str) -> Path:
    script_path = output_scene.parent / sync_script_name
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(default_sync_script_text(profile_path), encoding="utf-8")
    return script_path


def build_scene(
    model: Dict[str, Any],
    scene_config: Dict[str, Any],
    include_unused_assets_as_fixed: bool,
) -> str:
    robot = model.get("robot", {})
    base = model.get("base")
    if not base or not base.get("name"):
        fail("Viewer model has no base")

    scene_section = scene_config.get("scene", {})
    paths = scene_config.get("paths", {})
    nodes = scene_config.get("nodes", {})
    materials = scene_config.get("materials", {})

    root_name = node_name(scene_section.get("root_name") or robot.get("name", "HakoniwaRobot"))
    sync_script_res_path = paths.get("sync_script", "res://assets/tb3_reference_sync.gd")
    profile_path = paths.get("robot_sync_profile", "res://config/robot_sync.profile.json")
    endpoint_path = paths.get("endpoint_config", "res://config/endpoint_shm_poll_with_pdu.json")
    include_sim_node = bool(nodes.get("generate_sim_node", False))
    include_codec_node = bool(nodes.get("generate_codec_node", False))
    apply_default_materials = bool(materials.get("apply_default_materials", False))

    ext_count = len(model.get("assets", [])) + 1 + int(include_sim_node) + int(include_codec_node)
    sub_count = 3 + (4 if apply_default_materials else 0)
    load_steps = ext_count + sub_count + 1

    lines: List[str] = []
    emit_header(lines, load_steps)
    resource_ids = emit_ext_resources(
        lines=lines,
        model=model,
        scene_config=scene_config,
        sync_script_res_path=sync_script_res_path,
        include_sim_node=include_sim_node,
        include_codec_node=include_codec_node,
    )
    emit_template_environment(lines)
    material_ids = emit_default_materials(lines) if apply_default_materials else {}
    emit_ground_mesh(lines)

    emit_node(lines, root_name, "Node3D")
    lines.append("")

    emit_node(lines, "WorldEnvironment", "WorldEnvironment", parent=".")
    lines.append('environment = SubResource("Environment_default")')
    lines.append("")

    emit_node(lines, "Sun", "DirectionalLight3D", parent=".")
    lines.append(
        "transform = Transform3D(0.8034194, -0.47907954, 0.35355332, "
        "0.105737455, 0.69915634, 0.70710677, -0.5859495, -0.53071946, 0.61237246, "
        "0, 0.5482025, -1.7023231)"
    )
    lines.append("light_energy = 0.909")
    lines.append("light_indirect_energy = 0.2")
    lines.append("shadow_enabled = true")
    lines.append("")

    emit_node(lines, "HakoSync", "Node", parent=".")
    lines.append(f'script = ExtResource("{resource_ids["__sync_script__"]}")')
    lines.append(f'profile_path = "{profile_path}"')
    lines.append("")

    emit_node(lines, "RosToGodot", "Node3D", parent=".")
    lines.append(f"transform = {transform_ros_to_godot_line()}")
    lines.append("")

    emit_node(lines, "Visuals", "Node3D", parent="RosToGodot")
    lines.append("")

    base_body_name = base["name"]
    base_name = node_name(base_body_name)
    base_path = f"RosToGodot/Visuals/{base_name}"

    emit_node(lines, base_name, "Node3D", parent="RosToGodot/Visuals")
    base_xyz = base.get("mount", {}).get("xyz", [0.0, 0.0, 0.0])
    base_rpy = base.get("mount", {}).get("rpy", [0.0, 0.0, 0.0])
    if any(abs(float(v)) > 1e-12 for v in base_xyz):
        lines.append(f"position = {vec3(base_xyz)}")
    if any(abs(float(v)) > 1e-12 for v in base_rpy):
        lines.append(f"rotation = {vec3(base_rpy)}")
    lines.append("")

    base_asset_id = base.get("asset", base_body_name)
    emit_model_instance(lines, base_path, base_asset_id, resource_ids)
    if apply_default_materials and base_asset_id in material_ids:
        lines.append(
            f'[node name="{base_asset_id}_visual_0" parent="{base_path}/model/{base_name}" index="0"]'
        )
        lines.append(f'surface_material_override/0 = SubResource("{material_ids[base_asset_id]}")')
        lines.append("")

    node_paths = {base_body_name: base_path}
    used_asset_ids: Set[str] = {base_asset_id}

    emit_parts_with_parent_resolution(
        lines=lines,
        parts=model.get("movable_parts", []),
        section_name="movable_parts",
        base_body_name=base_body_name,
        node_paths=node_paths,
        resource_ids=resource_ids,
        material_ids=material_ids,
        apply_default_materials=apply_default_materials,
        used_asset_ids=used_asset_ids,
    )
    emit_parts_with_parent_resolution(
        lines=lines,
        parts=model.get("fixed_parts", []),
        section_name="fixed_parts",
        base_body_name=base_body_name,
        node_paths=node_paths,
        resource_ids=resource_ids,
        material_ids=material_ids,
        apply_default_materials=apply_default_materials,
        used_asset_ids=used_asset_ids,
    )

    if include_unused_assets_as_fixed:
        for asset in model.get("assets", []):
            asset_id = asset["id"]
            if asset_id in used_asset_ids:
                continue
            emit_node(lines, node_name(asset_id), "Node3D", parent=base_path)
            lines.append("position = Vector3(0, 0, 0)")
            lines.append("rotation = Vector3(0, 0, 0)")
            lines.append("")
            emit_model_instance(lines, f"{base_path}/{node_name(asset_id)}", asset_id, resource_ids)

    emit_node(lines, "Ground", "Node3D", parent=".")
    lines.append("transform = Transform3D(20, 0, 0, 0, 20, 0, 0, 0, 20, 0, -0.0021769702, 0)")
    lines.append("")
    emit_node(lines, "MeshInstance3D", "MeshInstance3D", parent="Ground")
    lines.append(
        "transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -0.00034930857, 0.007932744, 0.0012831822)"
    )
    lines.append('mesh = SubResource("PlaneMesh_csd54")')
    lines.append("")

    if include_sim_node:
        emit_node(lines, "HakoniwaSimNode", "Node", parent=".")
        lines.append(f'script = ExtResource("{resource_ids["__sim_node__"]}")')
        lines.append('asset_name = "GodotTB3"')
        lines.append("use_internal_shm_endpoint = true")
        lines.append(f'shm_endpoint_config_path = "{endpoint_path}"')
        if include_codec_node:
            lines.append('codec_node_path = NodePath("../HakoniwaCodecNode")')
        lines.append("auto_initialize_on_ready = true")
        lines.append("auto_tick_on_physics_process = true")
        lines.append("enable_physics_time_sync = true")
        lines.append('metadata/_custom_type_script = "res://addons/hakoniwa/scripts/hakoniwa_simulation_node.gd"')
        lines.append("")

    if include_codec_node:
        emit_node(lines, "HakoniwaCodecNode", "Node", parent=".")
        lines.append(f'script = ExtResource("{resource_ids["__codec_node__"]}")')
        lines.append('metadata/_custom_type_script = "res://addons/hakoniwa/scripts/hakoniwa_codec_node.gd"')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def infer_scene_config_path(model_path: Path) -> Optional[Path]:
    body_dir = model_path.resolve().parent.parent
    candidate = body_dir / "config" / "godot_scene.yaml"
    if candidate.is_file():
        return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Godot .tscn scene from hako_viewer_model.json")
    parser.add_argument("model", type=Path, help="Path to hako_viewer_model.json")
    parser.add_argument("-o", "--out", type=Path, required=True, help="Output .tscn path")
    parser.add_argument("--scene-config", type=Path, default=None, help="Optional godot_scene.yaml path")
    parser.add_argument(
        "--no-unused-assets",
        action="store_true",
        help="Do not attach assets that are not referenced by base/movable_parts/fixed_parts",
    )
    parser.add_argument(
        "--sync-script",
        default=None,
        help="Deprecated compatibility option. The generated script name is taken from godot_scene.yaml when present.",
    )
    parser.add_argument(
        "--res-root",
        default=None,
        help="Deprecated compatibility option. Asset paths are taken from godot_scene.yaml when present.",
    )
    args = parser.parse_args()

    model = load_model(args.model)
    scene_config_path = args.scene_config or infer_scene_config_path(args.model)
    scene_config = load_scene_config(scene_config_path)

    scene = build_scene(
        model=model,
        scene_config=scene_config,
        include_unused_assets_as_fixed=not args.no_unused_assets,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(scene, encoding="utf-8")

    sync_script_name = scene_config.get("scene", {}).get("sync_script_name") or args.sync_script
    if sync_script_name:
        profile_path = scene_config.get("paths", {}).get("robot_sync_profile", "res://config/robot_sync.profile.json")
        script_path = write_sync_script(args.out, sync_script_name, profile_path)
        print(f"Successfully wrote {script_path}")

    print(f"Successfully wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
