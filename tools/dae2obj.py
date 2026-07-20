#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def import_trimesh_module():
    try:
        import trimesh
    except ModuleNotFoundError:
        fail(
            "'trimesh' Python package not found. "
            "Install it with: python3 -m pip install trimesh"
        )

    return trimesh


def build_output_path(
    input_file: Path,
    output_arg: str | None,
) -> Path:
    if output_arg:
        return Path(output_arg)

    return input_file.with_suffix(".obj")


def convert_dae_to_obj(
    input_file: Path,
    output_file: Path,
) -> None:
    trimesh = import_trimesh_module()

    print(f"Converting {input_file} -> {output_file}")

    try:
        loaded = trimesh.load(
            input_file,
            file_type="dae",
            force="scene",
            process=False,
        )
    except ModuleNotFoundError as exc:
        fail(
            "DAE support requires the 'pycollada' package. "
            "Install it with: python3 -m pip install pycollada\n"
            f"Details: {exc}"
        )
    except Exception as exc:
        fail(
            f"Failed to load DAE file '{input_file}': {exc}"
        )

    #
    # A DAE file may contain multiple geometries and scene transforms.
    # Convert the complete scene into a single mesh so that transforms
    # are preserved in the generated OBJ.
    #
    try:
        if isinstance(loaded, trimesh.Scene):
            mesh = loaded.to_mesh()
        elif isinstance(loaded, trimesh.Trimesh):
            mesh = loaded
        else:
            fail(
                f"Unsupported mesh type loaded from '{input_file}': "
                f"{type(loaded).__name__}"
            )
    except Exception as exc:
        fail(
            f"Failed to convert DAE scene into mesh: {exc}"
        )

    if mesh.is_empty:
        fail(
            f"No mesh geometry found in '{input_file}'"
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        mesh.export(
            output_file,
            file_type="obj",
        )
    except Exception as exc:
        fail(
            f"Failed to export OBJ file '{output_file}': {exc}"
        )

    print(f"Successfully wrote {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a COLLADA DAE mesh file into Wavefront OBJ."
    )

    parser.add_argument(
        "input",
        help="Path to the input .dae file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Path to the output .obj file. "
            "Defaults to the input path with the .obj extension."
        ),
    )

    args = parser.parse_args()

    input_file = Path(args.input)

    if not input_file.is_file():
        fail(
            f"Input file not found at '{input_file}'"
        )

    if input_file.suffix.lower() != ".dae":
        fail(
            f"Input file must have a .dae extension: '{input_file}'"
        )

    output_file = build_output_path(
        input_file,
        args.output,
    )

    convert_dae_to_obj(
        input_file,
        output_file,
    )


if __name__ == "__main__":
    main()
    