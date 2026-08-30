#!/usr/bin/env python3

"""Forge a reproducible Ackermann vehicle body from a narrow Recipe contract."""

from __future__ import annotations

import argparse
import filecmp
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"


class ForgeError(RuntimeError):
    pass


def require_mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ForgeError(f"{label} must be a mapping")
    return value


def load_recipe(body: str) -> tuple[Path, dict]:
    recipe_path = REPO_ROOT / "bodies" / body / "config" / "ackermann-forge.yaml"
    if not recipe_path.is_file():
        raise ForgeError(f"Ackermann Forge Recipe not found: {recipe_path}")
    recipe = require_mapping(yaml.safe_load(recipe_path.read_text(encoding="utf-8")), "Recipe")
    if recipe.get("version") != 1:
        raise ForgeError("Only Ackermann Forge Recipe version 1 is supported")
    if recipe.get("kind") != "ackermann_vehicle":
        raise ForgeError("Recipe kind must be 'ackermann_vehicle'")
    if recipe.get("body") != body:
        raise ForgeError(f"Recipe body must match requested body '{body}'")
    return recipe_path, recipe


def run_tool(name: str, *args: str | Path) -> None:
    command = [sys.executable, str(TOOLS_DIR / name), *(str(arg) for arg in args)]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def stage_paths(output_dir: Path, basename: str) -> dict[str, Path]:
    return {
        "structural": output_dir / f"{basename}.xml",
        "actuated": output_dir / f"{basename}.actuated.xml",
        "collision": output_dir / f"{basename}.actuated.collision.xml",
        "contact": output_dir / f"{basename}.actuated.collision.contact.xml",
        "world": output_dir / f"{basename}.minimal_world.xml",
    }


def normalize_file_resources(urdf_path: Path, source_root: Path) -> None:
    """Rewrite upstream file:// resources to deterministic source-relative paths."""
    tree = ET.parse(urdf_path)
    source_root = source_root.resolve()
    changed = 0
    for element in tree.getroot().iter():
        filename = element.get("filename")
        if not filename:
            continue
        parsed = urlparse(filename)
        if parsed.scheme != "file":
            continue
        if parsed.netloc not in ("", "localhost"):
            raise ForgeError(f"Unsupported non-local file URI: {filename}")
        resource = Path(unquote(parsed.path)).resolve()
        try:
            resource.relative_to(source_root)
        except ValueError as exc:
            raise ForgeError(
                f"file URI escapes materialized source root: {filename}"
            ) from exc
        element.set(
            "filename",
            os.path.relpath(resource, urdf_path.parent.resolve()),
        )
        changed += 1
    ET.indent(tree)
    tree.write(urdf_path, encoding="utf-8", xml_declaration=True)
    print(f"Normalized {changed} file URI resource reference(s) in {urdf_path}")


def remove_mimic_elements(urdf_path: Path, joint_names: list[str]) -> None:
    requested = set(joint_names)
    tree = ET.parse(urdf_path)
    found: set[str] = set()
    for joint in tree.getroot().findall("joint"):
        name = joint.get("name", "")
        if name not in requested:
            continue
        mimic = joint.find("mimic")
        if mimic is not None:
            joint.remove(mimic)
            found.add(name)
    missing = requested - found
    if missing:
        raise ForgeError("Configured mimic joint(s) were not found: " + ", ".join(sorted(missing)))
    ET.indent(tree)
    tree.write(urdf_path, encoding="utf-8", xml_declaration=True)
    if found:
        print("Removed mimic coupling from: " + ", ".join(sorted(found)))


def remove_top_level_elements(urdf_path: Path, element_names: list[str]) -> None:
    requested = set(element_names)
    tree = ET.parse(urdf_path)
    root = tree.getroot()
    removed: dict[str, int] = {name: 0 for name in requested}
    for child in list(root):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in requested:
            root.remove(child)
            removed[local_name] += 1
    missing = sorted(name for name, count in removed.items() if count == 0)
    if missing:
        raise ForgeError(
            "Configured top-level element(s) were not found: " + ", ".join(missing)
        )
    ET.indent(tree)
    tree.write(urdf_path, encoding="utf-8", xml_declaration=True)
    if removed:
        print(
            "Removed upstream simulator elements: "
            + ", ".join(f"{name}={removed[name]}" for name in sorted(removed))
        )


def materialize_xacro(
    body: str,
    source: dict,
    adaptations: dict,
    body_root: Path,
    output_dir: Path,
) -> tuple[Path, list[Path]]:
    definition = REPO_ROOT / str(source.get("definition", ""))
    entry_relative = Path(str(source.get("entry", "")))
    if not definition.is_file() or not entry_relative.as_posix():
        raise ForgeError("xacro source requires existing definition and entry")

    source_root = body_root / "source"
    run_tool("fetch.py", definition, "--output-dir", source_root)
    entry = source_root / entry_relative
    if not entry.is_file():
        raise ForgeError(f"Xacro entry not found after fetch: {entry}")

    basename = str(require_mapping(source.get("output", {}), "source.output").get("basename", body))
    urdf = output_dir / f"{basename}.urdf"
    command: list[str | Path] = [entry, "-o", urdf]
    packages = require_mapping(source.get("packages", {}), "source.packages")
    for package_name, relative_path in sorted(packages.items()):
        command.extend(["--package", f"{package_name}={source_root / str(relative_path)}"])
    run_tool("xacro2urdf.py", *command)
    normalize_file_resources(urdf, source_root)

    remove_mimics = adaptations.get("remove_mimic_joints", [])
    if not isinstance(remove_mimics, list) or not all(isinstance(item, str) for item in remove_mimics):
        raise ForgeError("adaptations.remove_mimic_joints must be a string list")
    remove_mimic_elements(urdf, remove_mimics)

    remove_elements = adaptations.get("remove_top_level_elements", [])
    if not isinstance(remove_elements, list) or not all(
        isinstance(item, str) for item in remove_elements
    ):
        raise ForgeError("adaptations.remove_top_level_elements must be a string list")
    remove_top_level_elements(urdf, remove_elements)

    conversion_input = urdf
    outputs = [urdf]
    if bool(source.get("convert_dae_to_obj", False)):
        obj_urdf = output_dir / f"{basename}.obj.urdf"
        run_tool("urdf_dae2obj.py", urdf, "-o", obj_urdf)
        conversion_input = obj_urdf
        outputs.append(obj_urdf)

    structural = output_dir / f"{basename}.xml"
    run_tool("urdf2mjcf.py", conversion_input, "-o", structural)
    outputs.append(structural)
    return structural, outputs


def materialize_local_mjcf(source: dict, canonical_body_root: Path, output_dir: Path) -> tuple[Path, list[Path]]:
    relative_path = Path(str(source.get("path", "")))
    source_model = canonical_body_root / relative_path
    if not source_model.is_file():
        raise ForgeError(f"Local MJCF source not found: {source_model}")
    basename = str(require_mapping(source.get("output", {}), "source.output").get("basename", source_model.stem))
    structural = output_dir / f"{basename}.xml"
    shutil.copy2(source_model, structural)
    return structural, [structural]


def apply_joint_dynamics(config_path: Path, structural: Path) -> None:
    """Apply explicit porting overrides without editing a generated MJCF."""
    if not config_path.is_file():
        return
    config = require_mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "joint_dynamics",
    )
    configured = require_mapping(config.get("joints"), "joint_dynamics.joints")
    tree = ET.parse(structural)
    joints = {
        element.get("name"): element
        for element in tree.getroot().findall(".//joint")
        if element.get("name")
    }
    missing = sorted(set(configured) - set(joints))
    if missing:
        raise ForgeError(
            "joint_dynamics.yaml references unknown joint(s): " + ", ".join(missing)
        )
    for joint_name, raw_attributes in configured.items():
        attributes = require_mapping(
            raw_attributes, f"joint_dynamics.joints.{joint_name}"
        )
        for key, value in attributes.items():
            if isinstance(value, list):
                rendered = " ".join(str(item) for item in value)
            elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
                rendered = str(value)
            else:
                raise ForgeError(
                    f"unsupported joint attribute {joint_name}.{key}: {value!r}"
                )
            joints[joint_name].set(key, rendered)
    ET.indent(tree)
    tree.write(structural, encoding="utf-8", xml_declaration=False)
    print(f"Applied joint dynamics from {config_path} -> {structural}")


def apply_visual_materials(config_path: Path, structural: Path) -> None:
    """Apply recipe-owned visual presentation without editing generated MJCF."""
    if not config_path.is_file():
        return
    run_tool(
        "mjcf_apply_visual_materials.py",
        structural,
        config_path,
        "--output",
        structural,
    )


def apply_overlays(canonical_config: Path, structural: Path, output_dir: Path) -> list[Path]:
    basename = structural.stem
    paths = stage_paths(output_dir, basename)
    outputs: list[Path] = []
    current = structural

    actuators = canonical_config / "actuators.yaml"
    if actuators.is_file():
        run_tool("mjcf_add_actuators.py", current, actuators, "--output", paths["actuated"])
        current = paths["actuated"]
        outputs.append(current)

    collision = canonical_config / "collision_primitives.yaml"
    if collision.is_file():
        run_tool("mjcf_apply_collision_primitives.py", current, collision, "--output", paths["collision"])
        current = paths["collision"]
        outputs.append(current)

    contact = canonical_config / "contact_excludes.yaml"
    if contact.is_file():
        run_tool("mjcf_add_contact_excludes.py", current, contact, "--output", paths["contact"])
        current = paths["contact"]
        outputs.append(current)

    world = canonical_config / "mujoco_world.yaml"
    if world.is_file():
        run_tool("mjcf_compose_world.py", current, world, "--output", paths["world"])
        outputs.append(paths["world"])

    return outputs


def forge_to(body: str, recipe: dict, body_root: Path, output_dir: Path) -> list[Path]:
    canonical_body_root = REPO_ROOT / "bodies" / body
    canonical_config = canonical_body_root / "config"
    output_dir.mkdir(parents=True, exist_ok=True)
    source = require_mapping(recipe.get("source"), "source")
    source_type = source.get("type")
    adaptations = require_mapping(recipe.get("adaptations", {}), "adaptations")

    if source_type == "local_mjcf":
        structural, outputs = materialize_local_mjcf(source, canonical_body_root, output_dir)
    elif source_type == "xacro":
        structural, outputs = materialize_xacro(
            body, source, adaptations, body_root, output_dir
        )
    else:
        raise ForgeError("source.type must be 'local_mjcf' or 'xacro'")

    apply_joint_dynamics(canonical_config / "joint_dynamics.yaml", structural)
    apply_visual_materials(canonical_config / "visual_materials.yaml", structural)
    outputs.extend(apply_overlays(canonical_config, structural, output_dir))
    print(f"Ackermann Forge complete: {body}")
    for output in outputs:
        print(f"  - {output}")
    return outputs


def verify(body: str, recipe: dict) -> None:
    expected_dir = REPO_ROOT / "bodies" / body / "generated"
    with tempfile.TemporaryDirectory(prefix=f"hakoniwa-ackermann-{body}-") as temporary:
        temp_body = Path(temporary) / "bodies" / body
        actual = forge_to(body, recipe, temp_body, temp_body / "generated")
        world_models = [path for path in actual if path.name.endswith(".minimal_world.xml")]
        if len(world_models) != 1:
            raise ForgeError("Forge verification requires exactly one minimal-world MJCF")
        try:
            import mujoco
        except ModuleNotFoundError as exc:
            raise ForgeError("MuJoCo Python package is required for verification") from exc
        model = mujoco.MjModel.from_xml_path(str(world_models[0]))
        print(
            "MuJoCo load passed: "
            f"nq={model.nq} nv={model.nv} nu={model.nu} ngeom={model.ngeom}"
        )
        if model.nu != 4:
            raise ForgeError(f"Ackermann model must expose four actuators, got {model.nu}")
        run_tool(
            "ackermann/validate.py",
            body,
            "--model",
            world_models[0],
        )
        mismatches: list[str] = []
        for actual_path in actual:
            expected_path = expected_dir / actual_path.name
            if not expected_path.is_file():
                mismatches.append(f"missing expected artifact: {expected_path}")
            elif not filecmp.cmp(actual_path, expected_path, shallow=False):
                mismatches.append(f"content differs: {expected_path.name}")
        if mismatches:
            raise ForgeError("Forge verification failed:\n  - " + "\n  - ".join(mismatches))
    print(f"Ackermann Forge verification passed: {body}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("body", help="Body name under bodies/")
    parser.add_argument("--verify", action="store_true", help="forge in a temporary body tree and compare with committed artifacts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _, recipe = load_recipe(args.body)
    if args.verify:
        verify(args.body, recipe)
    else:
        body_root = REPO_ROOT / "bodies" / args.body
        forge_to(args.body, recipe, body_root, body_root / "generated")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ForgeError, OSError, subprocess.CalledProcessError, ET.ParseError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
