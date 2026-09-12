#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


class ComposeError(RuntimeError):
    pass


MERGED_WORLD_SECTIONS = {"size", "asset", "worldbody"}
IGNORED_WORLD_SECTIONS = {"compiler", "option", "visual", "statistic"}
SUPPORTED_WORLD_SECTIONS = MERGED_WORLD_SECTIONS | IGNORED_WORLD_SECTIONS
FILE_BASE_ATTRS = {
    "mesh": "meshdir",
    "texture": "texturedir",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compose a robot MuJoCo XML and a world MuJoCo XML into one model. "
            "The robot model remains authoritative for global/runtime sections; "
            "the world contributes <size>, <asset>, and <worldbody> content."
        )
    )
    parser.add_argument("robot_model", help="Robot MuJoCo XML used as the base model")
    parser.add_argument("world_model", help="World MuJoCo XML to merge into the robot model")
    parser.add_argument("--output", "-o", required=True, help="Output composed MuJoCo XML")
    parser.add_argument(
        "--keep-robot-ground",
        action="store_true",
        help="Keep a top-level robot worldbody geom named 'ground' instead of removing it",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip loading the generated XML with MuJoCo after composition",
    )
    return parser.parse_args()


def _parse_mujoco(path: Path, label: str) -> ET.ElementTree:
    if not path.is_file():
        raise ComposeError(f"{label} not found: {path}")
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError) as exc:
        raise ComposeError(f"invalid {label}: {path}: {exc}") from exc
    if tree.getroot().tag != "mujoco":
        raise ComposeError(f"{label} root must be <mujoco>: {path}")
    return tree


def _require_worldbody(root: ET.Element, source: Path, label: str) -> ET.Element:
    worldbody = root.find("worldbody")
    if worldbody is None:
        raise ComposeError(f"{label} has no <worldbody>: {source}")
    return worldbody


def _validate_world_sections(root: ET.Element, source: Path) -> list[str]:
    unsupported = sorted({child.tag for child in root if child.tag not in SUPPORTED_WORLD_SECTIONS})
    if unsupported:
        raise ComposeError(
            "world model contains unsupported top-level section(s): "
            f"{', '.join(unsupported)}: {source}"
        )
    return [child.tag for child in root if child.tag in IGNORED_WORLD_SECTIONS]


def _insert_root_section_before_model_content(root: ET.Element, section: ET.Element) -> None:
    children = list(root)
    for tag in ("asset", "worldbody"):
        existing = root.find(tag)
        if existing is not None:
            root.insert(children.index(existing), section)
            return
    root.append(section)


def _numeric_size_value(raw: str, key: str, source: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ComposeError(f"non-numeric MuJoCo size attribute: {source}.{key}={raw!r}") from exc
    return value


def _format_numeric(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.12g}"


def _merge_size(robot_root: ET.Element, world_root: ET.Element) -> dict[str, str]:
    world_size = world_root.find("size")
    if world_size is None:
        return {}
    robot_size = robot_root.find("size")
    if robot_size is None:
        robot_size = ET.Element("size")
        _insert_root_section_before_model_content(robot_root, robot_size)

    merged: dict[str, str] = {}
    for key, world_raw in world_size.attrib.items():
        world_value = _numeric_size_value(world_raw, key, "world")
        robot_raw = robot_size.get(key)
        if robot_raw is None:
            selected = world_value
        else:
            selected = max(
                _numeric_size_value(robot_raw, key, "robot"),
                world_value,
            )
        formatted = _format_numeric(selected)
        robot_size.set(key, formatted)
        merged[key] = formatted
    return merged


def _compiler_asset_base(root: ET.Element, source: Path, element: ET.Element) -> Path:
    compiler = root.find("compiler")
    if compiler is None:
        return source.parent
    assetdir = compiler.get("assetdir")
    type_dir_attr = FILE_BASE_ATTRS.get(element.tag)
    type_dir = compiler.get(type_dir_attr) if type_dir_attr else None
    directory = type_dir or assetdir
    if not directory:
        return source.parent
    candidate = Path(directory)
    if candidate.is_absolute():
        return candidate
    return (source.parent / candidate).resolve()


def _normalize_asset_file_paths(
    asset: ET.Element | None,
    source_root: ET.Element,
    source_xml: Path,
    output_xml: Path,
) -> list[dict[str, str]]:
    rewritten: list[dict[str, str]] = []
    if asset is None:
        return rewritten
    output_dir = output_xml.parent.resolve()
    for element in asset.iter():
        file_value = element.get("file")
        if not file_value:
            continue
        source_path = Path(file_value)
        if not source_path.is_absolute():
            source_path = (_compiler_asset_base(source_root, source_xml, element) / source_path).resolve()
        if not source_path.exists():
            raise ComposeError(
                f"asset file not found for <{element.tag}>: {file_value} -> {source_path}"
            )
        normalized = os.path.relpath(source_path, output_dir)
        element.set("file", normalized)
        rewritten.append({"source": file_value, "resolved": str(source_path), "output": normalized})
    return rewritten


def _clear_compiler_asset_dirs(root: ET.Element) -> None:
    compiler = root.find("compiler")
    if compiler is None:
        return
    for attr in ("assetdir", "meshdir", "texturedir"):
        compiler.attrib.pop(attr, None)


def _name_key(element: ET.Element) -> tuple[str, str] | None:
    name = element.get("name")
    if not name:
        return None
    tag = "joint" if element.tag == "freejoint" else element.tag
    return tag, name


def _named_entries(section: ET.Element | None) -> dict[tuple[str, str], ET.Element]:
    entries: dict[tuple[str, str], ET.Element] = {}
    if section is None:
        return entries
    for element in section.iter():
        key = _name_key(element)
        if key is not None:
            entries[key] = element
    return entries


def _reject_name_collisions(
    robot_asset: ET.Element | None,
    robot_worldbody: ET.Element,
    world_asset: ET.Element | None,
    world_worldbody: ET.Element,
) -> None:
    robot_names = _named_entries(robot_asset)
    robot_names.update(_named_entries(robot_worldbody))
    world_names = _named_entries(world_asset)
    world_names.update(_named_entries(world_worldbody))
    collisions = sorted(set(robot_names) & set(world_names))
    if collisions:
        details = ", ".join(f"<{tag} name='{name}'>" for tag, name in collisions)
        raise ComposeError(f"named MuJoCo object collision(s): {details}")


def _ensure_asset(root: ET.Element) -> ET.Element:
    asset = root.find("asset")
    if asset is not None:
        return asset
    asset = ET.Element("asset")
    worldbody = root.find("worldbody")
    if worldbody is None:
        root.append(asset)
        return asset
    children = list(root)
    root.insert(children.index(worldbody), asset)
    return asset


def _remove_robot_ground(worldbody: ET.Element) -> int:
    removed = 0
    for geom in list(worldbody.findall("geom")):
        if geom.get("name") == "ground":
            worldbody.remove(geom)
            removed += 1
    return removed


def compose_mujoco_world(
    robot_model: Path,
    world_model: Path,
    output: Path,
    *,
    keep_robot_ground: bool = False,
) -> dict[str, object]:
    robot_model = robot_model.expanduser().resolve()
    world_model = world_model.expanduser().resolve()
    output = output.expanduser().resolve()
    if output in {robot_model, world_model}:
        raise ComposeError("output must differ from both input XML files")

    robot_tree = _parse_mujoco(robot_model, "robot model")
    world_tree = _parse_mujoco(world_model, "world model")
    robot_root = robot_tree.getroot()
    world_root = world_tree.getroot()
    ignored_world_sections = _validate_world_sections(world_root, world_model)

    robot_worldbody = _require_worldbody(robot_root, robot_model, "robot model")
    world_worldbody = _require_worldbody(world_root, world_model, "world model")
    robot_asset = robot_root.find("asset")
    world_asset = world_root.find("asset")

    removed_ground = 0 if keep_robot_ground else _remove_robot_ground(robot_worldbody)
    _reject_name_collisions(robot_asset, robot_worldbody, world_asset, world_worldbody)
    merged_size = _merge_size(robot_root, world_root)

    output.parent.mkdir(parents=True, exist_ok=True)
    robot_asset_rewrites = _normalize_asset_file_paths(
        robot_asset, robot_root, robot_model, output
    )
    world_asset_copy = copy.deepcopy(world_asset) if world_asset is not None else None
    world_asset_rewrites = _normalize_asset_file_paths(
        world_asset_copy, world_root, world_model, output
    )
    _clear_compiler_asset_dirs(robot_root)

    added_assets = 0
    if world_asset_copy is not None and len(world_asset_copy):
        destination_asset = _ensure_asset(robot_root)
        for child in list(world_asset_copy):
            destination_asset.append(child)
            added_assets += 1

    added_worldbody_children = 0
    for child in list(world_worldbody):
        robot_worldbody.insert(added_worldbody_children, copy.deepcopy(child))
        added_worldbody_children += 1

    ET.indent(robot_tree, space="  ")
    robot_tree.write(output, encoding="utf-8", xml_declaration=True)

    return {
        "robot_model": str(robot_model),
        "world_model": str(world_model),
        "output": str(output),
        "removed_robot_ground_geoms": removed_ground,
        "merged_size": merged_size,
        "added_world_assets": added_assets,
        "added_worldbody_children": added_worldbody_children,
        "robot_asset_rewrites": robot_asset_rewrites,
        "world_asset_rewrites": world_asset_rewrites,
        "ignored_world_sections": ignored_world_sections,
    }


def validate_with_mujoco(output: Path) -> None:
    try:
        import mujoco  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ComposeError(
            "MuJoCo Python package is required for validation; install requirements.txt "
            "or pass --no-validate"
        ) from exc
    try:
        mujoco.MjModel.from_xml_path(str(output))
    except Exception as exc:  # MuJoCo exposes parser/compiler failures as runtime errors.
        raise ComposeError(f"MuJoCo validation failed for {output}: {exc}") from exc


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    try:
        receipt = compose_mujoco_world(
            Path(args.robot_model),
            Path(args.world_model),
            output,
            keep_robot_ground=args.keep_robot_ground,
        )
        if not args.no_validate:
            validate_with_mujoco(output.expanduser().resolve())
    except ComposeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if receipt["ignored_world_sections"]:
        sections = ", ".join(str(value) for value in receipt["ignored_world_sections"])
        print(
            "[WARN] world global section(s) are not imported; robot model remains "
            f"authoritative: {sections}",
            file=sys.stderr,
        )
    print(f"Generated {receipt['output']}")
    print(
        "Composition: "
        f"world_assets={receipt['added_world_assets']} "
        f"worldbody_children={receipt['added_worldbody_children']} "
        f"removed_robot_ground={receipt['removed_robot_ground_geoms']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
