#!/usr/bin/env python3

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from dae2obj import convert_dae_to_obj


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def build_output_path(
    input_file: Path,
    output_arg: str | None,
) -> Path:
    if output_arg:
        return Path(output_arg)

    return input_file.with_name(
        f"{input_file.stem}.obj.urdf"
    )


def resolve_mesh_path(
    urdf_file: Path,
    mesh_filename: str,
) -> Path:
    mesh_path = Path(mesh_filename).expanduser()

    if mesh_path.is_absolute():
        return mesh_path.resolve()

    return (
        urdf_file.resolve().parent
        / mesh_path
    ).resolve()


def convert_urdf_dae_to_obj(
    input_file: Path,
    output_file: Path,
) -> None:
    try:
        tree = ET.parse(input_file)
    except ET.ParseError as exc:
        fail(
            f"Failed to parse URDF file "
            f"'{input_file}': {exc}"
        )

    root = tree.getroot()

    converted_count = 0
    converted_files: set[Path] = set()

    for element in root.iter():
        filename = element.get("filename")

        if not filename:
            continue

        #
        # Only convert DAE mesh references.
        #
        if Path(filename).suffix.lower() != ".dae":
            continue

        dae_path = resolve_mesh_path(
            input_file,
            filename,
        )

        if not dae_path.is_file():
            fail(
                f"DAE mesh file not found.\n"
                f"  URDF reference: {filename}\n"
                f"  Resolved path:  {dae_path}"
            )

        obj_path = dae_path.with_suffix(".obj")

        #
        # Avoid converting the same DAE multiple times when
        # multiple URDF elements reference the same mesh.
        #
        if dae_path not in converted_files:
            convert_dae_to_obj(
                dae_path,
                obj_path,
            )
            converted_files.add(dae_path)

        #
        # Preserve the original path style.
        #
        # Example:
        #   ../meshes/FR5WM/visual/base_link.dae
        #
        # becomes:
        #   ../meshes/FR5WM/visual/base_link.obj
        #
        new_filename = str(
            Path(filename).with_suffix(".obj")
        )

        element.set(
            "filename",
            new_filename,
        )

        print(
            f"Rewriting mesh reference: "
            f"{filename} -> {new_filename}"
        )

        converted_count += 1

    if converted_count == 0:
        print(
            f"No DAE mesh references found in "
            f"{input_file}"
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        ET.indent(tree)
        tree.write(
            output_file,
            encoding="utf-8",
            xml_declaration=True,
        )
    except Exception as exc:
        fail(
            f"Failed to write URDF file "
            f"'{output_file}': {exc}"
        )

    print(
        f"Successfully wrote {output_file}"
    )
    print(
        f"Converted {len(converted_files)} "
        f"DAE mesh file(s)"
    )
    print(
        f"Rewrote {converted_count} "
        f"URDF mesh reference(s)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert DAE meshes referenced by a URDF "
            "to OBJ and rewrite the URDF mesh references."
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
            "Path to the output URDF file. "
            "Defaults to <input-stem>.obj.urdf."
        ),
    )

    args = parser.parse_args()

    input_file = Path(args.input)

    if not input_file.is_file():
        fail(
            f"Input file not found at "
            f"'{input_file}'"
        )

    output_file = build_output_path(
        input_file,
        args.output,
    )

    convert_urdf_dae_to_obj(
        input_file,
        output_file,
    )


if __name__ == "__main__":
    main()