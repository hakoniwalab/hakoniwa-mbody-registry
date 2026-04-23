#!/usr/bin/env python3

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from path_utils import infer_generated_dir


SUPPORTED_ACTUATOR_TYPES = {
    "motor",
    "position",
    "velocity",
    "intvelocity",
    "damper",
    "cylinder",
    "muscle",
    "adhesion",
    "general",
}


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def load_yaml_config(config_file: Path) -> list[dict]:
    with config_file.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)

    if not isinstance(config, dict):
        fail("Actuator config root must be a mapping.")

    actuators = config.get("actuators")
    if not isinstance(actuators, list) or not actuators:
        fail("Actuator config must contain a non-empty 'actuators' list.")

    normalized: list[dict] = []
    for index, actuator in enumerate(actuators):
        if not isinstance(actuator, dict):
            fail(f"Actuator entry #{index} must be a mapping.")

        actuator_type = actuator.get("type")
        name = actuator.get("name")
        joint = actuator.get("joint")

        if not isinstance(actuator_type, str) or actuator_type not in SUPPORTED_ACTUATOR_TYPES:
            fail(f"Actuator entry #{index} has unsupported type '{actuator_type}'.")
        if not isinstance(name, str) or not name.strip():
            fail(f"Actuator entry #{index} must define a non-empty 'name'.")
        if not isinstance(joint, str) or not joint.strip():
            fail(f"Actuator entry #{index} must define a non-empty 'joint'.")

        normalized.append(actuator)

    return normalized


def build_output_path(input_file: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)

    generated_dir = infer_generated_dir(input_file)
    if generated_dir is None:
        return input_file.with_name(f"{input_file.stem}.actuated{input_file.suffix}")
    return generated_dir / f"{input_file.stem}.actuated{input_file.suffix}"


def find_joint_names(root: ET.Element) -> set[str]:
    return {
        joint.get("name")
        for joint in root.findall(".//joint")
        if joint.get("name")
    }


def stringify_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if isinstance(value, str):
        return value
    fail(f"Unsupported actuator attribute value type: {type(value).__name__}")


def apply_actuators(mjcf_file: Path, config_file: Path, output_file: Path) -> None:
    tree = ET.parse(mjcf_file)
    root = tree.getroot()
    actuators_config = load_yaml_config(config_file)
    joint_names = find_joint_names(root)

    missing_joints = sorted(
        {
            actuator["joint"]
            for actuator in actuators_config
            if actuator["joint"] not in joint_names
        }
    )
    if missing_joints:
        fail(f"Actuator config references unknown joints: {', '.join(missing_joints)}")

    actuator_element = root.find("actuator")
    if actuator_element is None:
        actuator_element = ET.SubElement(root, "actuator")
    else:
        actuator_element.clear()

    for actuator in actuators_config:
        actuator_type = actuator["type"]
        element = ET.SubElement(actuator_element, actuator_type)
        for key, value in actuator.items():
            if key == "type":
                continue
            element.set(key, stringify_value(value))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    tree.write(output_file, encoding="utf-8", xml_declaration=False)
    print(f"Applied {len(actuators_config)} actuators from {config_file} -> {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add MuJoCo actuator definitions to an MJCF XML model from a YAML configuration."
    )
    parser.add_argument("input", help="Path to the input MJCF XML file.")
    parser.add_argument("config", help="Path to the actuator YAML file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output MJCF XML file. Defaults to bodies/{name}/generated/{stem}.actuated.xml when the input is under bodies/{name}/.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    config_file = Path(args.config)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")
    if not config_file.is_file():
        fail(f"Config file not found at {config_file}")

    output_file = build_output_path(input_file, args.output)
    apply_actuators(input_file, config_file, output_file)


if __name__ == "__main__":
    main()
