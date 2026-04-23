#!/usr/bin/env python3

import argparse
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


PACKAGE_URI_PATTERN = re.compile(r"^package://([^/]+)/(.+)$")


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def import_mujoco_module():
    try:
        import mujoco
    except ModuleNotFoundError:
        fail("'mujoco' Python package not found. Install it with: python3 -m pip install mujoco")
    return mujoco


def parse_package_roots(raw_args: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for raw_arg in raw_args:
        if "=" not in raw_arg:
            fail(f"Invalid --package-root '{raw_arg}'. Use PACKAGE=/absolute/or/relative/path format.")
        package_name, raw_path = raw_arg.split("=", 1)
        package_name = package_name.strip()
        if not package_name:
            fail(f"Invalid --package-root '{raw_arg}'. Package name must not be empty.")
        package_path = Path(raw_path).expanduser().resolve()
        if not package_path.is_dir():
            fail(f"Package root for '{package_name}' does not exist: {package_path}")
        roots[package_name] = package_path
    return roots


def build_output_path(input_file: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)
    return input_file.with_suffix(".xml")


def discover_package_root(package_name: str, input_file: Path, explicit_roots: dict[str, Path]) -> Path | None:
    if package_name in explicit_roots:
        return explicit_roots[package_name]

    resolved_input = input_file.resolve()
    for parent in resolved_input.parents:
        if parent.name == package_name:
            return parent
    return None


def rewrite_package_uris(
    input_file: Path,
    explicit_roots: dict[str, Path],
) -> tuple[ET.ElementTree, bool]:
    tree = ET.parse(input_file)
    root = tree.getroot()
    modified = False

    for element in root.iter():
        filename = element.get("filename")
        if not filename:
            continue

        match = PACKAGE_URI_PATTERN.match(filename)
        if not match:
            continue

        package_name, relative_resource = match.groups()
        package_root = discover_package_root(package_name, input_file, explicit_roots)
        if package_root is None:
            fail(
                f"Could not resolve package URI '{filename}'. "
                f"Pass --package-root {package_name}=PATH or place the URDF under a directory named '{package_name}'."
            )

        target_path = package_root / relative_resource
        if not target_path.exists():
            fail(f"Resolved package URI '{filename}' to missing path: {target_path}")

        element.set("filename", target_path.resolve().as_posix())
        modified = True

    return tree, modified


def ensure_mujoco_compiler_block(root: ET.Element) -> None:
    mujoco_element = root.find("mujoco")
    if mujoco_element is None:
        mujoco_element = ET.SubElement(root, "mujoco")

    compiler_element = mujoco_element.find("compiler")
    if compiler_element is None:
        compiler_element = ET.SubElement(mujoco_element, "compiler")

    if "discardvisual" not in compiler_element.attrib:
        compiler_element.set("discardvisual", "false")


def prepare_urdf_for_mujoco(input_file: Path, explicit_roots: dict[str, Path]) -> Path:
    tree, _ = rewrite_package_uris(input_file, explicit_roots)
    root = tree.getroot()
    ensure_mujoco_compiler_block(root)

    temporary_dir = Path(tempfile.mkdtemp(prefix="urdf2mjcf-"))
    temporary_urdf = temporary_dir / input_file.name
    tree.write(temporary_urdf, encoding="utf-8", xml_declaration=True)
    return temporary_urdf


def save_last_xml(mujoco, model, output_file: Path) -> None:
    mujoco.mj_saveLastXML(str(output_file), model)


def convert_urdf_to_mjcf(input_file: Path, output_file: Path, explicit_roots: dict[str, Path]) -> None:
    mujoco = import_mujoco_module()
    prepared_urdf = prepare_urdf_for_mujoco(input_file, explicit_roots)

    print(f"Converting {input_file} -> {output_file}")
    try:
        model = mujoco.MjModel.from_xml_path(str(prepared_urdf))
    except Exception as exc:
        fail(f"MuJoCo failed to load URDF: {exc}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        save_last_xml(mujoco, model, output_file)
    except Exception as exc:
        fail(f"MuJoCo failed to save MJCF: {exc}")

    print(f"Successfully wrote {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a URDF file into canonical MJCF using MuJoCo's official compiler."
    )
    parser.add_argument("input", help="Path to the input URDF file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output MJCF XML file. Defaults to INPUT.xml.",
    )
    parser.add_argument(
        "--package-root",
        action="append",
        default=[],
        metavar="PACKAGE=PATH",
        help="Resolve package://PACKAGE/... URIs against PATH. Repeat for multiple packages.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    output_file = build_output_path(input_file, args.output)
    package_roots = parse_package_roots(args.package_root)
    convert_urdf_to_mjcf(input_file, output_file, package_roots)


if __name__ == "__main__":
    main()
