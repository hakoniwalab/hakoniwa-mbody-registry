#!/usr/bin/env python3
"""
Validate Hakoniwa view-model recipe YAML files.

The recipe is the human-authored input used by hako_viewer_model_gen.py.
This validator checks the recipe shape and verifies that referenced MJCF
bodies and joints exist.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc


class ValidationError(Exception):
    """Raised when a recipe file is invalid."""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


def load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid YAML in {path}: {exc}") from exc


def expect_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected object, got {type(value).__name__}")
    return value


def expect_array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{path}: expected array, got {type(value).__name__}")
    return value


def expect_string(value: Any, path: str, *, min_length: int = 0) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{path}: expected string, got {type(value).__name__}")
    if len(value) < min_length:
        raise ValidationError(f"{path}: expected string length >= {min_length}")
    return value


def expect_version(value: Any, path: str) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = expect_string(value, path, min_length=1)
    if not re.match(r"^[0-9]+\.[0-9]+$", text):
        raise ValidationError(f"{path}: expected MAJOR.MINOR format, got '{text}'")
    return text


def require_keys(obj: dict[str, Any], path: str, keys: Iterable[str]) -> None:
    for key in keys:
        if key not in obj:
            raise ValidationError(f"{path}: missing required key '{key}'")


def reject_extra_keys(obj: dict[str, Any], path: str, allowed: set[str]) -> None:
    extra = set(obj) - allowed
    if extra:
        keys = ", ".join(sorted(extra))
        raise ValidationError(f"{path}: unexpected key(s): {keys}")


def expect_string_list(value: Any, path: str) -> list[str]:
    arr = expect_array(value, path)
    out = []
    for i, item in enumerate(arr):
        out.append(expect_string(item, f"{path}[{i}]", min_length=1))
    return out


def resolve_path(path_value: str, base_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def collect_mjcf_names(mjcf_path: Path) -> tuple[set[str], set[str]]:
    try:
        root = ET.parse(mjcf_path).getroot()
    except FileNotFoundError as exc:
        raise ValidationError(f"MJCF file not found: {mjcf_path}") from exc
    except ET.ParseError as exc:
        raise ValidationError(f"invalid MJCF XML in {mjcf_path}: {exc}") from exc

    bodies: set[str] = set()
    joints: set[str] = set()

    for body in root.findall(".//body"):
        name = body.get("name")
        if name:
            bodies.add(name)

    for joint in root.findall(".//joint"):
        name = joint.get("name")
        if name:
            joints.add(name)

    return bodies, joints


def validate_recipe(recipe: Any, recipe_path: Path) -> list[str]:
    obj = expect_object(recipe, "$")
    require_keys(obj, "$", ["format", "version", "mjcf", "assets", "base"])
    reject_extra_keys(
        obj,
        "$",
        {
            "format",
            "version",
            "robot",
            "mjcf",
            "assets",
            "base",
            "movables",
            "movable_joints",
            "fixed_bodies",
            "coordinate_system",
            "coordinate",
        },
    )

    fmt = expect_string(obj["format"], "$.format", min_length=1)
    if fmt != "hako_viewer_model_recipe":
        raise ValidationError(
            f"$.format: expected 'hako_viewer_model_recipe', got '{fmt}'"
        )

    expect_version(obj["version"], "$.version")

    if "robot" in obj:
        expect_string(obj["robot"], "$.robot", min_length=1)

    mjcf_value = expect_string(obj["mjcf"], "$.mjcf", min_length=1)
    mjcf_path = resolve_path(mjcf_value, recipe_path.parent)

    assets = expect_object(obj["assets"], "$.assets")
    require_keys(assets, "$.assets", ["glb_dir", "map"])
    reject_extra_keys(assets, "$.assets", {"glb_dir", "map"})
    expect_string(assets["glb_dir"], "$.assets.glb_dir", min_length=1)
    mapping = expect_string(assets["map"], "$.assets.map", min_length=1)
    if mapping != "body_name":
        raise ValidationError(f"$.assets.map: expected 'body_name', got '{mapping}'")

    base = expect_string(obj["base"], "$.base", min_length=1)

    movables = []
    if "movables" in obj:
        movables.extend(expect_string_list(obj["movables"], "$.movables"))
    if "movable_joints" in obj:
        movables.extend(expect_string_list(obj["movable_joints"], "$.movable_joints"))

    fixed_bodies = []
    if "fixed_bodies" in obj:
        fixed_bodies.extend(expect_string_list(obj["fixed_bodies"], "$.fixed_bodies"))

    if "coordinate_system" in obj:
        expect_string(obj["coordinate_system"], "$.coordinate_system", min_length=1)
    if "coordinate" in obj:
        expect_string(obj["coordinate"], "$.coordinate", min_length=1)

    bodies, joints = collect_mjcf_names(mjcf_path)

    if base not in bodies:
        raise ValidationError(f"$.base: body '{base}' not found in MJCF: {mjcf_path}")

    for joint in movables:
        if joint not in joints:
            raise ValidationError(
                f"movable joint '{joint}' not found in MJCF: {mjcf_path}"
            )

    for body in fixed_bodies:
        if body not in bodies:
            raise ValidationError(
                f"fixed body '{body}' not found in MJCF: {mjcf_path}"
            )

    warnings = []
    if "actuated" in mjcf_path.name:
        warnings.append(
            f"recipe points to a runtime-customized MJCF: {mjcf_path.name}; "
            "prefer structural MJCF for the normal mbody flow"
        )

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Hakoniwa view-model recipe YAML files."
    )
    parser.add_argument(
        "recipes",
        nargs="+",
        type=Path,
        help="Path(s) to viewer.recipe.yaml file(s) to validate.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/view-model-recipe.schema.json"),
        help="Path to the recipe schema file. The schema is loaded to ensure it exists, but validation is implemented without third-party dependencies.",
    )
    args = parser.parse_args()

    # Load the schema file as a smoke check so missing or invalid schema files fail fast.
    load_json(args.schema)

    ok = True
    for path in args.recipes:
        try:
            warnings = validate_recipe(load_yaml(path), path.resolve())
        except ValidationError as exc:
            ok = False
            print(f"NG: {path}: {exc}", file=sys.stderr)
        else:
            print(f"OK: {path}")
            for warning in warnings:
                print(f"WARN: {path}: {warning}", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
