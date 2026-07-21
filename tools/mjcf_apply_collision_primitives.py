#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from path_utils import infer_generated_dir


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        fail("Collision primitive config root must be a mapping.")
    return data


def build_output_path(input_file: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)

    generated_dir = infer_generated_dir(input_file)
    output_name = f"{input_file.stem}.collision{input_file.suffix}"
    if generated_dir is None:
        return input_file.with_name(output_name)
    return generated_dir / output_name


def find_bodies(root: ET.Element) -> dict[str, ET.Element]:
    return {
        body.get("name"): body
        for body in root.findall(".//body")
        if body.get("name")
    }


def normalize_attr_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if isinstance(value, str):
        return value
    fail(f"Unsupported geom attribute value type: {type(value).__name__}")


def body_matches(pattern: str, body_name: str) -> bool:
    return pattern == "*" or pattern == body_name


def apply_disable_existing(root: ET.Element, rules: list[dict]) -> int:
    changed = 0
    for rule_index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            fail(f"disable_existing entry #{rule_index} must be a mapping.")

        body_pattern = rule.get("body", "*")
        geom_type = rule.get("type")
        if not isinstance(body_pattern, str) or not body_pattern:
            fail(f"disable_existing entry #{rule_index} has invalid body.")
        if geom_type is not None and not isinstance(geom_type, str):
            fail(f"disable_existing entry #{rule_index} has invalid type.")

        for body in root.findall(".//body"):
            body_name = body.get("name") or ""
            if not body_matches(body_pattern, body_name):
                continue
            for geom in body.findall("geom"):
                if geom_type is not None and geom.get("type") != geom_type:
                    continue
                geom.set("contype", "0")
                geom.set("conaffinity", "0")
                changed += 1
    return changed


def apply_additional_geoms(root: ET.Element, geoms: list[dict]) -> int:
    bodies = find_bodies(root)
    added = 0

    for index, entry in enumerate(geoms):
        if not isinstance(entry, dict):
            fail(f"geoms entry #{index} must be a mapping.")

        body_name = entry.get("body")
        attrs = entry.get("attrs")
        if not isinstance(body_name, str) or not body_name:
            fail(f"geoms entry #{index} must define a non-empty body.")
        if not isinstance(attrs, dict):
            fail(f"geoms entry #{index} must define attrs mapping.")

        body = bodies.get(body_name)
        if body is None:
            fail(f"geoms entry #{index} references unknown body: {body_name}")

        normalized_attrs = {
            str(key): normalize_attr_value(value)
            for key, value in attrs.items()
        }
        if "type" not in normalized_attrs:
            fail(f"geoms entry #{index} attrs must define type.")
        if "name" not in normalized_attrs:
            normalized_attrs["name"] = f"{body_name}_collision"

        ET.SubElement(body, "geom", normalized_attrs)
        added += 1

    return added


def apply_collision_primitives(input_file: Path, config_file: Path, output_file: Path) -> None:
    tree = ET.parse(input_file)
    root = tree.getroot()
    config = load_yaml(config_file)

    disabled = apply_disable_existing(root, config.get("disable_existing", []))
    added = apply_additional_geoms(root, config.get("geoms", []))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(output_file, encoding="utf-8", xml_declaration=False)
    print(
        f"Applied collision primitives from {config_file} -> {output_file} "
        f"(disabled={disabled}, added={added})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply simple MuJoCo collision primitive overrides to an MJCF XML model."
    )
    parser.add_argument("input", help="Path to the input MJCF XML file.")
    parser.add_argument("config", help="Path to the collision primitive YAML file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output MJCF XML path. Defaults to bodies/{name}/generated/{stem}.collision.xml when possible.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    config_file = Path(args.config)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")
    if not config_file.is_file():
        fail(f"Config file not found at {config_file}")

    apply_collision_primitives(
        input_file,
        config_file,
        build_output_path(input_file, args.output),
    )


if __name__ == "__main__":
    main()
