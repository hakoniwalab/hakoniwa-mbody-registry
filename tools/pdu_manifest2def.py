#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from path_utils import infer_generated_dir


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def build_output_path(input_file: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)

    generated_dir = infer_generated_dir(input_file)
    if generated_dir is None:
        return input_file.with_name("pdu_def.json")
    return generated_dir / "pdu_def.json"


def load_manifest(manifest_file: Path) -> dict:
    with manifest_file.open("r", encoding="utf-8") as file_obj:
        manifest = yaml.safe_load(file_obj)

    if not isinstance(manifest, dict):
        fail("Manifest root must be a mapping.")
    if manifest.get("format") != "hako_pdu_manifest":
        fail("Manifest 'format' must be 'hako_pdu_manifest'.")
    robot_name = manifest.get("robot_name")
    if not isinstance(robot_name, str) or not robot_name.strip():
        fail("Manifest must define a non-empty 'robot_name'.")
    return manifest


def default_pdutypes_id(robot_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", robot_name.strip().lower()).strip("-")
    if not slug:
        slug = "default"
    return f"{slug}-endpoint"


def generate_pdudef(
    manifest_file: Path,
    output_file: Path,
    pdutypes_path: str,
    pdutypes_id: str | None,
) -> None:
    manifest = load_manifest(manifest_file)
    robot_name = manifest["robot_name"]
    resolved_pdutypes_id = pdutypes_id or default_pdutypes_id(robot_name)

    pdudef = {
        "paths": [
            {
                "id": resolved_pdutypes_id,
                "path": pdutypes_path,
            }
        ],
        "robots": [
            {
                "name": robot_name,
                "pdutypes_id": resolved_pdutypes_id,
            }
        ],
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(pdudef, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_file} with 1 robot entry")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate compact Hakoniwa pdu_def.json from a pdu-manifest.yaml file."
    )
    parser.add_argument("input", help="Path to the input pdu-manifest.yaml file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output pdu_def.json file. Defaults to bodies/{name}/generated/pdu_def.json when the input is under bodies/{name}/.",
    )
    parser.add_argument(
        "--pdutypes-path",
        default="pdutypes.json",
        help="Relative path to the pdutypes.json file recorded in pdu_def.json.",
    )
    parser.add_argument(
        "--pdutypes-id",
        help="Override paths[].id / robots[].pdutypes_id. Defaults to '<robot-name>-endpoint'.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    output_file = build_output_path(input_file, args.output)
    generate_pdudef(
        manifest_file=input_file,
        output_file=output_file,
        pdutypes_path=args.pdutypes_path,
        pdutypes_id=args.pdutypes_id,
    )


if __name__ == "__main__":
    main()
