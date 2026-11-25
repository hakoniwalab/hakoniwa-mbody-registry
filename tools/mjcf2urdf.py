#!/usr/bin/env python3
"""Export the kinematic frames of an MJCF body subtree as URDF."""

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from path_utils import default_generated_file


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def parse_values(text: str | None, default: tuple[float, ...]) -> tuple[float, ...]:
    if not text:
        return default
    values = tuple(float(value) for value in text.split())
    if len(values) != len(default) or not all(math.isfinite(value) for value in values):
        raise ValueError(f"Expected {len(default)} finite values, got '{text}'")
    return values


def rpy_from_quat(w: float, x: float, y: float, z: float) -> tuple[float, float, float]:
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm == 0:
        raise ValueError("Quaternion must be nonzero")
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


class Defaults:
    """MJCF joint defaults indexed by class, including inherited attributes."""

    def __init__(self, model: ET.Element):
        self.joints: dict[str, dict[str, str]] = {}
        for top in model.findall("default"):
            self._walk(top, {})

    def _walk(self, element: ET.Element, inherited: dict[str, str]) -> None:
        attrs = inherited.copy()
        joint = element.find("joint")
        if joint is not None:
            attrs.update(joint.attrib)
        self.joints[element.get("class", "main")] = attrs
        for child in element.findall("default"):
            self._walk(child, attrs)

    def resolve(self, joint: ET.Element, body_class: str | None) -> dict[str, str]:
        joint_class = joint.get("class") or body_class or "main"
        return self.joints.get("main", {}) | self.joints.get(joint_class, {}) | joint.attrib


def body_joint(body: ET.Element) -> ET.Element | None:
    joints = [child for child in body if child.tag in ("joint", "freejoint")]
    if len(joints) > 1:
        fail(f"Body '{body.get('name')}': more than one joint")
    return joints[0] if joints else None


def convert(input_file: Path, root_name: str, robot_name: str) -> str:
    tree = ET.parse(input_file).getroot()
    defaults = Defaults(tree)
    root = next((body for body in tree.iter("body") if body.get("name") == root_name), None)
    if root is None:
        fail(f"Body '{root_name}' not found in {input_file}")

    # Selecting a subtree keeps the defaults inherited from its ancestors.
    parents = {child: body for body in tree.iter("body") for child in body.findall("body")}
    ancestor = root
    root_class = root.get("childclass")
    while not root_class and ancestor in parents:
        ancestor = parents[ancestor]
        root_class = ancestor.get("childclass")

    body_joint(root)
    urdf = ET.Element("robot", name=robot_name)
    ET.SubElement(urdf, "link", name=root_name)

    def walk(body: ET.Element, body_class: str | None) -> None:
        for child in body.findall("body"):
            name = child.get("name")
            if not name:
                fail(f"Unnamed body under '{body.get('name')}'")
            ET.SubElement(urdf, "link", name=name)
            child_class = child.get("childclass") or body_class
            source_joint = body_joint(child)
            hinge = False
            if source_joint is not None and source_joint.tag == "joint":
                attrs = defaults.resolve(source_joint, child_class)
                hinge = attrs.get("type", "hinge") == "hinge"

            if hinge:
                if not attrs.get("name"):
                    fail(f"Hinge joint in body '{name}' must have a name")
                joint = ET.SubElement(urdf, "joint", name=attrs["name"], type="revolute")
            else:
                joint = ET.SubElement(urdf, "joint", name=f"{name}_fixed", type="fixed")

            pos = parse_values(child.get("pos"), (0.0, 0.0, 0.0))
            rpy = rpy_from_quat(*parse_values(child.get("quat"), (1.0, 0.0, 0.0, 0.0)))
            ET.SubElement(joint, "parent", link=body.get("name"))
            ET.SubElement(joint, "child", link=name)
            ET.SubElement(joint, "origin", xyz=" ".join(f"{value:.6g}" for value in pos),
                          rpy=" ".join(f"{value:.6g}" for value in rpy))
            if hinge:
                axis = parse_values(attrs.get("axis"), (0.0, 0.0, 1.0))
                lower, upper = parse_values(attrs.get("range"), (-math.pi, math.pi))
                ET.SubElement(joint, "axis", xyz=" ".join(f"{value:g}" for value in axis))
                ET.SubElement(joint, "limit", lower=f"{lower:g}", upper=f"{upper:g}",
                              effort="1000", velocity="10")
            walk(child, child_class)

    walk(root, root_class)
    ET.indent(urdf)
    return '<?xml version="1.0"?>\n' + ET.tostring(urdf, encoding="unicode") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export MJCF body frames and hinge joints as a geometry-free URDF.",
        epilog="Uses body pos and quat with hinge axes at the body origin and ranges in radians.",
    )
    parser.add_argument("input", help="Path to the input MJCF XML file.")
    parser.add_argument("root", help="Name of the root MJCF body to export.")
    parser.add_argument("--robot", default="robot", help="Name of the URDF robot (default: robot).")
    parser.add_argument(
        "-o", "--output",
        help="Path to the URDF file. Defaults to bodies/{name}/generated/<input stem>.urdf "
             "for registry bodies and <input stem>.urdf beside other inputs.",
    )
    args = parser.parse_args()
    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    output_file = Path(args.output) if args.output else default_generated_file(input_file, ".urdf")
    try:
        result = convert(input_file, args.root, args.robot)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(result, encoding="utf-8")
    except (ET.ParseError, OSError, ValueError) as error:
        fail(str(error))
    print(f"Generated {output_file}")


if __name__ == "__main__":
    main()
