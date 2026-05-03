#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
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
        return input_file.with_name("endpoint_shm_with_pdu.json")
    return generated_dir / "endpoint_shm_with_pdu.json"


def load_sync_config(config_file: Path) -> dict:
    with config_file.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)

    if not isinstance(config, dict):
        fail("Godot sync config root must be a mapping.")
    if config.get("format") != "hako_godot_sync":
        fail("Godot sync config 'format' must be 'hako_godot_sync'.")
    robot_name = config.get("robot_name")
    if not isinstance(robot_name, str) or not robot_name.strip():
        fail("Godot sync config must define a non-empty 'robot_name'.")
    endpoint = config.get("endpoint")
    if not isinstance(endpoint, dict):
        fail("Godot sync config must define an 'endpoint' mapping.")
    endpoint_name = endpoint.get("endpoint_name")
    if not isinstance(endpoint_name, str) or not endpoint_name.strip():
        fail("'endpoint.endpoint_name' must be a non-empty string.")
    comm_path = endpoint.get("comm_path")
    if not isinstance(comm_path, str) or not comm_path.strip():
        fail("'endpoint.comm_path' must be a non-empty string.")
    pdu = config.get("pdu")
    if not isinstance(pdu, dict):
        fail("Godot sync config must define a 'pdu' mapping.")
    for key in ("base", "joints"):
        value = pdu.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"'pdu.{key}' must be a non-empty string.")
    return config


def resolve_reference_path(raw_path: str, config_dir: Path, output_dir: Path) -> str:
    source_path = Path(raw_path)
    if source_path.is_absolute():
        resolved = source_path
        return os.path.relpath(resolved, output_dir)
    return raw_path


def normalize_pdudef_path(raw_path: str, output_dir: Path) -> str:
    source_path = Path(raw_path)
    if source_path.is_absolute():
        return os.path.relpath(source_path, output_dir)
    return raw_path


def generate_endpoint(
    config_file: Path,
    output_file: Path,
    pdu_def_path: str,
    cache_path: str,
) -> None:
    config = load_sync_config(config_file)
    endpoint = config["endpoint"]
    config_dir = config_file.resolve().parent
    output_dir = output_file.resolve().parent

    endpoint_json = {
        "name": endpoint["endpoint_name"],
        "pdu_def_path": normalize_pdudef_path(pdu_def_path, output_dir),
        "cache": cache_path,
        "comm": resolve_reference_path(endpoint["comm_path"], config_dir, output_dir),
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(endpoint_json, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_file} for robot {config['robot_name']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Godot internal endpoint_shm_with_pdu.json from godot_sync.yaml."
    )
    parser.add_argument("input", help="Path to the input godot_sync.yaml file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output endpoint JSON file. Defaults to bodies/{name}/generated/endpoint_shm_with_pdu.json when the input is under bodies/{name}/.",
    )
    parser.add_argument(
        "--pdu-def-path",
        default="pdu_def.json",
        help="Path to the pdu_def.json file. Relative paths are embedded as-is. Absolute paths are rewritten relative to the output file.",
    )
    parser.add_argument(
        "--cache-path",
        default="cache/buffer.json",
        help="Cache JSON path to embed in the endpoint config.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    output_file = build_output_path(input_file, args.output)
    generate_endpoint(
        config_file=input_file,
        output_file=output_file,
        pdu_def_path=args.pdu_def_path,
        cache_path=args.cache_path,
    )


if __name__ == "__main__":
    main()
