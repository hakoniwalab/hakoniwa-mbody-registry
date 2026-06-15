#!/usr/bin/env python3
"""
Validate Hakoniwa view-model JSON files against the repository schema.

This validator intentionally avoids third-party dependencies so it can be used
as a lightweight smoke check in local development and CI.

It validates the subset of JSON Schema currently used by
schemas/view-model.schema.json and adds a few semantic checks that are useful
for generated view-model files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


class ValidationError(Exception):
    """Raised when a view-model file is invalid."""


Vec3 = list[int | float]


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc


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


def expect_number(value: Any, path: str) -> int | float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{path}: expected number, got {type(value).__name__}")
    return value


def expect_vec3(value: Any, path: str) -> Vec3:
    arr = expect_array(value, path)
    if len(arr) != 3:
        raise ValidationError(f"{path}: expected vec3 with exactly 3 numbers")
    return [expect_number(v, f"{path}[{i}]") for i, v in enumerate(arr)]


def require_keys(obj: dict[str, Any], path: str, keys: Iterable[str]) -> None:
    for key in keys:
        if key not in obj:
            raise ValidationError(f"{path}: missing required key '{key}'")


def reject_extra_keys(obj: dict[str, Any], path: str, allowed: set[str]) -> None:
    extra = set(obj) - allowed
    if extra:
        keys = ", ".join(sorted(extra))
        raise ValidationError(f"{path}: unexpected key(s): {keys}")


def validate_asset(value: Any, path: str) -> str:
    obj = expect_object(value, path)
    require_keys(obj, path, ["id", "type", "path"])
    reject_extra_keys(obj, path, {"id", "type", "path"})

    asset_id = expect_string(obj["id"], f"{path}.id", min_length=1)
    asset_type = expect_string(obj["type"], f"{path}.type", min_length=1)
    if asset_type != "glb":
        raise ValidationError(f"{path}.type: expected 'glb', got '{asset_type}'")
    expect_string(obj["path"], f"{path}.path", min_length=1)
    return asset_id


def validate_mount(value: Any, path: str) -> None:
    obj = expect_object(value, path)
    require_keys(obj, path, ["xyz", "rpy"])
    reject_extra_keys(obj, path, {"xyz", "rpy"})
    expect_vec3(obj["xyz"], f"{path}.xyz")
    expect_vec3(obj["rpy"], f"{path}.rpy")


def validate_motion(value: Any, path: str) -> None:
    obj = expect_object(value, path)
    require_keys(obj, path, ["type"])
    reject_extra_keys(obj, path, {"type", "axis"})

    motion_type = expect_string(obj["type"], f"{path}.type", min_length=1)
    allowed = {"continuous", "revolute", "prismatic", "free", "ball"}
    if motion_type not in allowed:
        raise ValidationError(
            f"{path}.type: expected one of {sorted(allowed)}, got '{motion_type}'"
        )

    if motion_type in {"continuous", "revolute", "prismatic"}:
        if "axis" not in obj:
            raise ValidationError(f"{path}: motion type '{motion_type}' requires axis")
        expect_vec3(obj["axis"], f"{path}.axis")
    elif "axis" in obj:
        expect_vec3(obj["axis"], f"{path}.axis")


def validate_part(value: Any, path: str, asset_ids: set[str]) -> None:
    obj = expect_object(value, path)
    require_keys(obj, path, ["name", "asset", "mount"])
    reject_extra_keys(obj, path, {"name", "parent", "asset", "mount"})

    expect_string(obj["name"], f"{path}.name", min_length=1)
    if "parent" in obj and obj["parent"] is not None:
        expect_string(obj["parent"], f"{path}.parent", min_length=1)

    asset = expect_string(obj["asset"], f"{path}.asset", min_length=1)
    if asset not in asset_ids:
        raise ValidationError(f"{path}.asset: unknown asset id '{asset}'")

    validate_mount(obj["mount"], f"{path}.mount")


def validate_movable_part(value: Any, path: str, asset_ids: set[str]) -> None:
    obj = expect_object(value, path)
    require_keys(obj, path, ["name", "joint", "asset", "mount", "motion"])
    reject_extra_keys(obj, path, {"name", "joint", "parent", "asset", "mount", "motion"})

    # Validate the common part shape first.
    validate_part(
        {
            "name": obj["name"],
            **({"parent": obj["parent"]} if "parent" in obj else {}),
            "asset": obj["asset"],
            "mount": obj["mount"],
        },
        path,
        asset_ids,
    )
    expect_string(obj["joint"], f"{path}.joint", min_length=1)
    validate_motion(obj["motion"], f"{path}.motion")


def validate_view_model(model: Any) -> None:
    obj = expect_object(model, "$")
    required = ["format", "version", "coordinate_system", "robot", "assets", "base"]
    require_keys(obj, "$", required)
    reject_extra_keys(
        obj,
        "$",
        {
            "format",
            "version",
            "coordinate_system",
            "robot",
            "assets",
            "base",
            "movable_parts",
            "fixed_parts",
        },
    )

    fmt = expect_string(obj["format"], "$.format", min_length=1)
    if fmt != "hako_viewer_model":
        raise ValidationError(f"$.format: expected 'hako_viewer_model', got '{fmt}'")

    version = expect_string(obj["version"], "$.version", min_length=1)
    if not re.match(r"^[0-9]+\.[0-9]+$", version):
        raise ValidationError(f"$.version: expected MAJOR.MINOR format, got '{version}'")

    expect_string(obj["coordinate_system"], "$.coordinate_system", min_length=1)

    robot = expect_object(obj["robot"], "$.robot")
    require_keys(robot, "$.robot", ["name", "root"])
    reject_extra_keys(robot, "$.robot", {"name", "root"})
    expect_string(robot["name"], "$.robot.name", min_length=1)
    root = expect_string(robot["root"], "$.robot.root", min_length=1)

    assets = expect_array(obj["assets"], "$.assets")
    asset_ids: set[str] = set()
    for i, asset in enumerate(assets):
        asset_id = validate_asset(asset, f"$.assets[{i}]")
        if asset_id in asset_ids:
            raise ValidationError(f"$.assets[{i}].id: duplicate asset id '{asset_id}'")
        asset_ids.add(asset_id)

    validate_part(obj["base"], "$.base", asset_ids)
    base_name = expect_string(obj["base"]["name"], "$.base.name", min_length=1)
    if base_name != root:
        raise ValidationError(
            f"$.base.name: expected robot root '{root}', got '{base_name}'"
        )

    movable_parts = expect_array(obj.get("movable_parts", []), "$.movable_parts")
    for i, part in enumerate(movable_parts):
        validate_movable_part(part, f"$.movable_parts[{i}]", asset_ids)

    fixed_parts = expect_array(obj.get("fixed_parts", []), "$.fixed_parts")
    for i, part in enumerate(fixed_parts):
        validate_part(part, f"$.fixed_parts[{i}]", asset_ids)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Hakoniwa view-model JSON files."
    )
    parser.add_argument(
        "view_models",
        nargs="+",
        type=Path,
        help="Path(s) to view-model JSON file(s) to validate.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/view-model.schema.json"),
        help="Path to the schema file. The schema is loaded to ensure it exists, but validation is implemented without third-party dependencies.",
    )
    args = parser.parse_args()

    # Load the schema file as a smoke check so missing or invalid schema files fail fast.
    load_json(args.schema)

    ok = True
    for path in args.view_models:
        try:
            validate_view_model(load_json(path))
        except ValidationError as exc:
            ok = False
            print(f"NG: {path}: {exc}", file=sys.stderr)
        else:
            print(f"OK: {path}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
