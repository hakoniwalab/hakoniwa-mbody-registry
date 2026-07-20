#!/usr/bin/env python3

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from path_utils import default_generated_file, discover_package_dir


PACKAGE_URI_PATTERN = re.compile(r"^package://([^/]+)/(.+)$")


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def import_mujoco_module():
    try:
        import mujoco
    except ModuleNotFoundError:
        fail(
            "'mujoco' Python package not found. "
            "Install it with: python3 -m pip install mujoco"
        )
    return mujoco


def parse_package_roots(raw_args: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}

    for raw_arg in raw_args:
        if "=" not in raw_arg:
            fail(
                f"Invalid --package-root '{raw_arg}'. "
                "Use PACKAGE=/absolute/or/relative/path format."
            )

        package_name, raw_path = raw_arg.split("=", 1)
        package_name = package_name.strip()

        if not package_name:
            fail(
                f"Invalid --package-root '{raw_arg}'. "
                "Package name must not be empty."
            )

        package_path = Path(raw_path).expanduser().resolve()

        if not package_path.is_dir():
            fail(
                f"Package root for '{package_name}' "
                f"does not exist: {package_path}"
            )

        roots[package_name] = package_path

    return roots


def build_output_path(
    input_file: Path,
    output_arg: str | None,
) -> Path:
    if output_arg:
        return Path(output_arg)

    return default_generated_file(input_file, ".xml")


def discover_package_root(
    package_name: str,
    input_file: Path,
    explicit_roots: dict[str, Path],
) -> Path | None:
    if package_name in explicit_roots:
        return explicit_roots[package_name]

    registry_match = discover_package_dir(
        input_file,
        package_name,
    )

    if registry_match is not None:
        return registry_match

    resolved_input = input_file.resolve()

    for parent in resolved_input.parents:
        if parent.name == package_name:
            return parent

    return None


def rewrite_resource_paths(
    input_file: Path,
    explicit_roots: dict[str, Path],
) -> ET.ElementTree:
    """
    Rewrite resource paths in the URDF to absolute paths.

    Supports:

      package://PACKAGE/path/to/resource

    and normal relative paths such as:

      ../meshes/robot/link.dae

    Relative paths are resolved against the directory containing the
    original URDF file.
    """

    tree = ET.parse(input_file)
    root = tree.getroot()

    input_dir = input_file.resolve().parent

    for element in root.iter():
        filename = element.get("filename")

        if not filename:
            continue

        package_match = PACKAGE_URI_PATTERN.match(filename)

        if package_match:
            #
            # package://PACKAGE/path
            #
            package_name, relative_resource = package_match.groups()

            package_root = discover_package_root(
                package_name,
                input_file,
                explicit_roots,
            )

            if package_root is None:
                fail(
                    f"Could not resolve package URI '{filename}'. "
                    f"Pass --package-root {package_name}=PATH "
                    f"or place the URDF under a directory "
                    f"named '{package_name}'."
                )

            target_path = package_root / relative_resource

        else:
            #
            # Normal filesystem path.
            #
            resource_path = Path(filename).expanduser()

            if resource_path.is_absolute():
                target_path = resource_path
            else:
                #
                # Resolve relative paths against the ORIGINAL URDF.
                #
                target_path = input_dir / resource_path

        target_path = target_path.resolve()

        if not target_path.exists():
            fail(
                f"Resolved resource path '{filename}' "
                f"to missing path: {target_path}"
            )

        element.set(
            "filename",
            target_path.as_posix(),
        )

    return tree


def ensure_mujoco_compiler_block(
    root: ET.Element,
    discard_visual: bool,
) -> None:
    mujoco_element = root.find("mujoco")

    if mujoco_element is None:
        mujoco_element = ET.SubElement(
            root,
            "mujoco",
        )

    compiler_element = mujoco_element.find("compiler")

    if compiler_element is None:
        compiler_element = ET.SubElement(
            mujoco_element,
            "compiler",
        )

    if discard_visual:
        compiler_element.set(
            "discardvisual",
            "true",
        )
    elif "discardvisual" not in compiler_element.attrib:
        compiler_element.set(
            "discardvisual",
            "false",
        )

    if "fusestatic" not in compiler_element.attrib:
        compiler_element.set(
            "fusestatic",
            "false",
        )


def prepare_urdf_for_mujoco(
    input_file: Path,
    explicit_roots: dict[str, Path],
    discard_visual: bool,
) -> str:
    """
    Prepare the URDF as an XML string for MuJoCo.

    No temporary file is created.

    Resource paths are first converted to absolute paths so that
    MuJoCo can resolve meshes independently of the process working
    directory.
    """

    tree = rewrite_resource_paths(
        input_file,
        explicit_roots,
    )

    root = tree.getroot()

    ensure_mujoco_compiler_block(
        root,
        discard_visual,
    )

    return ET.tostring(
        root,
        encoding="unicode",
    )


def save_last_xml(
    mujoco,
    model,
    output_file: Path,
) -> None:
    mujoco.mj_saveLastXML(
        str(output_file),
        model,
    )


def normalize_mesh_paths(
    output_file: Path,
) -> None:
    """
    Convert absolute mesh paths in the generated MJCF back to paths
    relative to the generated MJCF file.

    This keeps the generated model portable.
    """

    tree = ET.parse(output_file)
    root = tree.getroot()

    output_dir = output_file.parent.resolve()
    modified = False

    for mesh in root.findall("./asset/mesh"):
        mesh_file = mesh.get("file")

        if not mesh_file:
            continue

        mesh_path = Path(mesh_file)

        if not mesh_path.is_absolute():
            continue

        relative_path = os.path.relpath(
            mesh_path,
            output_dir,
        )

        mesh.set(
            "file",
            relative_path,
        )

        modified = True

    if modified:
        ET.indent(tree)

        tree.write(
            output_file,
            encoding="utf-8",
            xml_declaration=False,
        )


def convert_urdf_to_mjcf(
    input_file: Path,
    output_file: Path,
    explicit_roots: dict[str, Path],
    discard_visual: bool,
) -> None:
    mujoco = import_mujoco_module()

    urdf_xml = prepare_urdf_for_mujoco(
        input_file,
        explicit_roots,
        discard_visual,
    )

    print(
        f"Converting {input_file} "
        f"-> {output_file}"
    )

    try:
        #
        # Load the processed URDF directly from memory.
        # No temporary URDF file is required.
        #
        model = mujoco.MjModel.from_xml_string(
            urdf_xml
        )

    except Exception as exc:
        fail(
            f"MuJoCo failed to load URDF: {exc}"
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        save_last_xml(
            mujoco,
            model,
            output_file,
        )

        normalize_mesh_paths(
            output_file,
        )

    except Exception as exc:
        fail(
            f"MuJoCo failed to save MJCF: {exc}"
        )

    print(
        f"Successfully wrote {output_file}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a URDF file into canonical MJCF "
            "using MuJoCo's official compiler."
        )
    )

    parser.add_argument(
        "input",
        help="Path to the input URDF file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Path to the output MJCF XML file. "
            "Defaults to bodies/{name}/generated/{stem}.xml "
            "when the input is under bodies/{name}/."
        ),
    )

    parser.add_argument(
        "--package-root",
        action="append",
        default=[],
        metavar="PACKAGE=PATH",
        help=(
            "Resolve package://PACKAGE/... URIs against PATH. "
            "Repeat for multiple packages."
        ),
    )

    parser.add_argument(
        "--discard-visual",
        action="store_true",
        help=(
            "Ask MuJoCo to discard URDF visual meshes "
            "during MJCF compilation."
        ),
    )

    args = parser.parse_args()

    input_file = Path(args.input)

    if not input_file.is_file():
        fail(
            f"Input file not found at {input_file}"
        )

    output_file = build_output_path(
        input_file,
        args.output,
    )

    package_roots = parse_package_roots(
        args.package_root,
    )

    convert_urdf_to_mjcf(
        input_file,
        output_file,
        package_roots,
        args.discard_visual,
    )


if __name__ == "__main__":
    main()