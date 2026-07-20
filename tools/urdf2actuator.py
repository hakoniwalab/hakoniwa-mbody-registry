#!/usr/bin/env python3

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    print("Error: 'PyYAML' package not found.", file=sys.stderr)
    print(
        "Please install it using: python3 -m pip install PyYAML",
        file=sys.stderr,
    )
    sys.exit(1)


SUPPORTED_JOINT_TYPES = {
    "revolute",
    "continuous",
    "prismatic",
}

SUPPORTED_ACTUATOR_TYPES = {
    "position",
    "velocity",
    "torque",
}


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def parse_float(
    value: str | None,
    field_name: str,
    joint_name: str,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except ValueError:
        fail(
            f"Invalid {field_name} value for joint "
            f"'{joint_name}': {value}"
        )


def build_position_actuator(
    joint_name: str,
    joint_type: str,
    limit: ET.Element | None,
    kp: float,
) -> dict:
    actuator = {
        "type": "position",
        "name": f"{joint_name}_motor",
        "joint": joint_name,
    }

    #
    # Continuous joints do not have position limits.
    #
    if joint_type == "continuous":
        actuator["ctrllimited"] = False

    else:
        if limit is None:
            print(
                f"Warning: Joint '{joint_name}' has no limit. "
                f"Position actuator will be created without ctrlrange.",
                file=sys.stderr,
            )
            actuator["ctrllimited"] = False

        else:
            lower = parse_float(
                limit.get("lower"),
                "lower",
                joint_name,
            )
            upper = parse_float(
                limit.get("upper"),
                "upper",
                joint_name,
            )

            if lower is None or upper is None:
                print(
                    f"Warning: Joint '{joint_name}' does not have "
                    f"both lower and upper limits. "
                    f"Position actuator will be created without ctrlrange.",
                    file=sys.stderr,
                )
                actuator["ctrllimited"] = False

            else:
                actuator["ctrllimited"] = True
                actuator["ctrlrange"] = [
                    lower,
                    upper,
                ]

    actuator["kp"] = kp

    return actuator


def build_velocity_actuator(
    joint_name: str,
    limit: ET.Element | None,
    kv: float,
) -> dict:
    actuator = {
        "type": "velocity",
        "name": f"{joint_name}_motor",
        "joint": joint_name,
    }

    velocity = None

    if limit is not None:
        velocity = parse_float(
            limit.get("velocity"),
            "velocity",
            joint_name,
        )

    if velocity is not None:
        velocity = abs(velocity)

        actuator["ctrllimited"] = True
        actuator["ctrlrange"] = [
            -velocity,
            velocity,
        ]
    else:
        print(
            f"Warning: Joint '{joint_name}' has no velocity limit. "
            f"Velocity actuator will be created without ctrlrange.",
            file=sys.stderr,
        )
        actuator["ctrllimited"] = False

    actuator["kv"] = kv

    return actuator


def build_torque_actuator(
    joint_name: str,
    limit: ET.Element | None,
) -> dict:
    actuator = {
        "type": "torque",
        "name": f"{joint_name}_motor",
        "joint": joint_name,
    }

    effort = None

    if limit is not None:
        effort = parse_float(
            limit.get("effort"),
            "effort",
            joint_name,
        )

    if effort is not None:
        effort = abs(effort)

        actuator["ctrllimited"] = True
        actuator["ctrlrange"] = [
            -effort,
            effort,
        ]
    else:
        print(
            f"Warning: Joint '{joint_name}' has no effort limit. "
            f"Torque actuator will be created without ctrlrange.",
            file=sys.stderr,
        )
        actuator["ctrllimited"] = False

    return actuator


def convert_urdf_to_actuator_yaml(
    input_file: Path,
    output_file: Path,
    actuator_type: str,
    kp: float,
    kv: float,
) -> None:
    try:
        tree = ET.parse(input_file)
    except ET.ParseError as exc:
        fail(
            f"Failed to parse URDF file "
            f"'{input_file}': {exc}"
        )

    root = tree.getroot()

    actuators: list[dict] = []

    for joint in root.findall("joint"):
        joint_name = joint.get("name")
        joint_type = joint.get("type")

        if not joint_name:
            print(
                "Warning: Joint without name was skipped.",
                file=sys.stderr,
            )
            continue

        if joint_type not in SUPPORTED_JOINT_TYPES:
            print(
                f"Skipping joint '{joint_name}' "
                f"with type '{joint_type}'."
            )
            continue

        limit = joint.find("limit")

        if actuator_type == "position":
            actuator = build_position_actuator(
                joint_name,
                joint_type,
                limit,
                kp,
            )

        elif actuator_type == "velocity":
            actuator = build_velocity_actuator(
                joint_name,
                limit,
                kv,
            )

        elif actuator_type == "torque":
            actuator = build_torque_actuator(
                joint_name,
                limit,
            )

        else:
            fail(
                f"Unsupported actuator type: "
                f"{actuator_type}"
            )

        actuators.append(actuator)

    if not actuators:
        fail(
            "No supported movable joints were found "
            f"in '{input_file}'."
        )

    output_data = {
        "actuators": actuators,
    }

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with output_file.open(
            "w",
            encoding="utf-8",
        ) as file_obj:
            yaml.safe_dump(
                output_data,
                file_obj,
                sort_keys=False,
                default_flow_style=False,
            )

    except Exception as exc:
        fail(
            f"Failed to write actuator YAML "
            f"'{output_file}': {exc}"
        )

    print(
        f"Successfully wrote {output_file}"
    )
    print(
        f"Generated {len(actuators)} "
        f"{actuator_type} actuator(s)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a MuJoCo actuator YAML definition "
            "from movable joints in a URDF file."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to the input URDF file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path to the output actuator YAML file.",
    )

    parser.add_argument(
        "--type",
        choices=sorted(SUPPORTED_ACTUATOR_TYPES),
        default="position",
        help=(
            "Actuator control type. "
            "Defaults to position."
        ),
    )

    parser.add_argument(
        "--kp",
        type=float,
        default=100.0,
        help=(
            "Position actuator gain. "
            "Defaults to 100.0."
        ),
    )

    parser.add_argument(
        "--kv",
        type=float,
        default=0.75,
        help=(
            "Velocity actuator gain. "
            "Defaults to 0.75."
        ),
    )

    args = parser.parse_args()

    if not args.input.is_file():
        fail(
            f"Input URDF file not found at "
            f"'{args.input}'"
        )

    if args.kp <= 0:
        fail("'--kp' must be greater than zero.")

    if args.kv <= 0:
        fail("'--kv' must be greater than zero.")

    convert_urdf_to_actuator_yaml(
        input_file=args.input,
        output_file=args.output,
        actuator_type=args.type,
        kp=args.kp,
        kv=args.kv,
    )


if __name__ == "__main__":
    main()