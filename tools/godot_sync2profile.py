#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from hako_godot_scene_gen import node_name
from path_utils import infer_generated_dir


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def build_output_path(input_file: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)

    generated_dir = infer_generated_dir(input_file)
    if generated_dir is None:
        return input_file.with_name("robot_sync.profile.json")
    return generated_dir / "godot" / "robot_sync.profile.json"


def load_sync_config(config_file: Path) -> dict:
    with config_file.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)

    if not isinstance(config, dict):
        fail("Godot sync config root must be a mapping.")
    if config.get("format") != "hako_godot_sync":
        fail("Godot sync config 'format' must be 'hako_godot_sync'.")
    robot_name = config.get("robot_name")
    if not isinstance(robot_name, str) or not robot_name.strip():
        fail("Godot sync config must define a non-empty 'robot_name'.")
    pdu = config.get("pdu")
    if not isinstance(pdu, dict):
        fail("Godot sync config must define a 'pdu' mapping.")
    for key in ("base", "joints"):
        value = pdu.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"'pdu.{key}' must be a non-empty string.")
    coordinate_system = config.get("coordinate_system")
    if not isinstance(coordinate_system, dict):
        fail("Godot sync config must define a 'coordinate_system' mapping.")
    for key in ("position_rule", "rotation_rule"):
        value = coordinate_system.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"'coordinate_system.{key}' must be a non-empty string.")
    joints = config.get("joints")
    if not isinstance(joints, list) or not joints:
        fail("Godot sync config must define a non-empty 'joints' list.")
    return config


def load_viewer_model(model_file: Path) -> dict[str, Any]:
    with model_file.open("r", encoding="utf-8") as file_obj:
        model = json.load(file_obj)
    if model.get("format") != "hako_viewer_model":
        fail("Viewer model 'format' must be 'hako_viewer_model'.")
    if not isinstance(model.get("base"), dict) or not model["base"].get("name"):
        fail("Viewer model must define 'base.name'.")
    return model


def build_visual_node_paths(model: dict[str, Any]) -> dict[str, str]:
    base_body_name = model["base"]["name"]
    node_paths: dict[str, str] = {
        base_body_name: f"Visuals/{node_name(base_body_name)}",
    }

    pending = list(model.get("movable_parts", [])) + list(model.get("fixed_parts", []))
    while pending:
        progressed = False
        remaining: list[dict[str, Any]] = []

        for part in pending:
            part_body = part.get("name")
            if not isinstance(part_body, str) or not part_body:
                fail("Viewer model part entry must define a non-empty 'name'.")
            parent_body = part.get("parent") or base_body_name
            if parent_body not in node_paths:
                remaining.append(part)
                continue

            parent_path = node_paths[parent_body]
            node_paths[part_body] = f"{parent_path}/{node_name(part_body)}"
            progressed = True

        if not remaining:
            break
        if not progressed:
            unresolved = ", ".join(
                f"{part.get('name')} -> {part.get('parent') or base_body_name}" for part in remaining
            )
            fail(f"Could not resolve viewer model parent paths: {unresolved}")
        pending = remaining

    return node_paths


def build_joint_mappings(sync_config: dict, node_paths: dict[str, str]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for index, joint in enumerate(sync_config["joints"]):
        context = f"joints[{index}]"
        if not isinstance(joint, dict):
            fail(f"{context} must be a mapping.")
        joint_name = joint.get("joint_name")
        body_name = joint.get("body_name")
        axis = joint.get("axis")
        sign = joint.get("sign")
        offset_rad = joint.get("offset_rad")

        if not isinstance(joint_name, str) or not joint_name.strip():
            fail(f"{context}.joint_name must be a non-empty string.")
        if not isinstance(body_name, str) or not body_name.strip():
            fail(f"{context}.body_name must be a non-empty string.")
        if body_name not in node_paths:
            fail(f"{context}.body_name '{body_name}' was not found in the viewer model.")
        if axis not in ("x", "y", "z"):
            fail(f"{context}.axis must be one of x, y, z.")
        if not isinstance(sign, (int, float)):
            fail(f"{context}.sign must be numeric.")
        if not isinstance(offset_rad, (int, float)):
            fail(f"{context}.offset_rad must be numeric.")

        mappings.append(
            {
                "joint_name": joint_name,
                "node_path": node_paths[body_name],
                "axis": axis,
                "sign": float(sign),
                "offset_rad": float(offset_rad),
                "apply_mode": "basis_delta",
            }
        )
    return mappings


def generate_profile(sync_file: Path, model_file: Path, output_file: Path) -> None:
    sync_config = load_sync_config(sync_file)
    model = load_viewer_model(model_file)
    node_paths = build_visual_node_paths(model)

    base_body_name = model["base"]["name"]
    profile = {
        "version": 1,
        "robot_name": sync_config["robot_name"],
        "base_link_pdu_name": sync_config["pdu"]["base"],
        "joint_states_pdu_name": sync_config["pdu"]["joints"],
        "base_node_path": node_paths[base_body_name],
        "coordinate_system": {
            "position_rule": sync_config["coordinate_system"]["position_rule"],
            "rotation_rule": sync_config["coordinate_system"]["rotation_rule"],
        },
        "joint_mappings": build_joint_mappings(sync_config, node_paths),
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_file} with {len(profile['joint_mappings'])} joint mappings")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate robot_sync.profile.json from godot_sync.yaml and a viewer model JSON."
    )
    parser.add_argument("sync", help="Path to the input godot_sync.yaml file.")
    parser.add_argument("model", help="Path to the input hako_viewer_model JSON file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output robot_sync.profile.json file. Defaults to bodies/{name}/generated/godot/robot_sync.profile.json when the sync config is under bodies/{name}/.",
    )
    args = parser.parse_args()

    sync_file = Path(args.sync)
    model_file = Path(args.model)
    if not sync_file.is_file():
        fail(f"Sync config not found at {sync_file}")
    if not model_file.is_file():
        fail(f"Viewer model not found at {model_file}")

    output_file = build_output_path(sync_file, args.output)
    generate_profile(sync_file, model_file, output_file)


if __name__ == "__main__":
    main()
