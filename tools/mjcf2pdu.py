#!/usr/bin/env python3

import argparse
import json
import sys
import xml.etree.ElementTree as ET
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
        return input_file.with_name("pdutypes.json")
    return generated_dir / "pdutypes.json"


def load_body_names(mjcf_file: Path) -> set[str]:
    root = ET.parse(mjcf_file).getroot()
    return {
        body.get("name")
        for body in root.findall(".//body")
        if body.get("name")
    }


def load_config(config_file: Path) -> dict:
    with config_file.open("r", encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)

    if not isinstance(config, dict):
        fail("PDU config root must be a mapping.")
    if not isinstance(config.get("bodies"), list) or not config["bodies"]:
        fail("PDU config must contain a non-empty 'bodies' list.")

    return config


def normalize_entry(raw_entry, defaults: dict, next_channel_id: int) -> tuple[dict, int]:
    if isinstance(raw_entry, str):
        entry = {"body": raw_entry}
    elif isinstance(raw_entry, dict):
        entry = dict(raw_entry)
    else:
        fail("Each PDU body entry must be either a string or a mapping.")

    body = entry.get("body")
    if not isinstance(body, str) or not body.strip():
        fail("Each PDU body entry must define a non-empty 'body'.")

    channel_id = entry.get("channel_id", next_channel_id)
    if not isinstance(channel_id, int):
        fail(f"PDU entry for body '{body}' has non-integer channel_id.")

    pdu_size = entry.get("pdu_size", defaults["default_pdu_size"])
    if not isinstance(pdu_size, int):
        fail(f"PDU entry for body '{body}' has non-integer pdu_size.")

    pdu_type = entry.get("type", defaults["default_type"])
    if not isinstance(pdu_type, str) or not pdu_type.strip():
        fail(f"PDU entry for body '{body}' has invalid type.")

    name_suffix = entry.get("name_suffix", defaults["default_name_suffix"])
    if not isinstance(name_suffix, str) or not name_suffix.strip():
        fail(f"PDU entry for body '{body}' has invalid name_suffix.")

    name = entry.get("name", f"{body}_{name_suffix}")
    if not isinstance(name, str) or not name.strip():
        fail(f"PDU entry for body '{body}' has invalid name.")

    normalized = {
        "channel_id": channel_id,
        "pdu_size": pdu_size,
        "name": name,
        "type": pdu_type,
        "body": body,
    }
    return normalized, max(next_channel_id, channel_id + 1)


def generate_pdutypes(mjcf_file: Path, config_file: Path, output_file: Path) -> None:
    config = load_config(config_file)
    body_names = load_body_names(mjcf_file)

    defaults = {
        "base_channel_id": config.get("base_channel_id", 0),
        "default_pdu_size": config.get("default_pdu_size", 72),
        "default_type": config.get("default_type", "geometry_msgs/Twist"),
        "default_name_suffix": config.get("default_name_suffix", "pos"),
    }

    if not isinstance(defaults["base_channel_id"], int):
        fail("'base_channel_id' must be an integer.")
    if not isinstance(defaults["default_pdu_size"], int):
        fail("'default_pdu_size' must be an integer.")
    if not isinstance(defaults["default_type"], str) or not defaults["default_type"].strip():
        fail("'default_type' must be a non-empty string.")
    if not isinstance(defaults["default_name_suffix"], str) or not defaults["default_name_suffix"].strip():
        fail("'default_name_suffix' must be a non-empty string.")

    pdutypes = []
    next_channel_id = defaults["base_channel_id"]
    used_channel_ids: set[int] = set()
    used_names: set[str] = set()

    for raw_entry in config["bodies"]:
        entry, next_channel_id = normalize_entry(raw_entry, defaults, next_channel_id)
        body = entry["body"]
        if body not in body_names:
            fail(f"PDU config references unknown MJCF body '{body}'.")
        if entry["channel_id"] in used_channel_ids:
            fail(f"Duplicate channel_id detected: {entry['channel_id']}")
        if entry["name"] in used_names:
            fail(f"Duplicate PDU name detected: {entry['name']}")

        used_channel_ids.add(entry["channel_id"])
        used_names.add(entry["name"])
        pdutypes.append(
            {
                "channel_id": entry["channel_id"],
                "pdu_size": entry["pdu_size"],
                "name": entry["name"],
                "type": entry["type"],
            }
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(pdutypes, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_file} with {len(pdutypes)} PDU entries")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Hakoniwa pdutypes.json from an MJCF body list and a YAML mapping."
    )
    parser.add_argument("input", help="Path to the input MJCF XML file.")
    parser.add_argument("config", help="Path to the PDU YAML file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output pdutypes.json file. Defaults to bodies/{name}/generated/pdutypes.json when the input is under bodies/{name}/.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    config_file = Path(args.config)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")
    if not config_file.is_file():
        fail(f"Config file not found at {config_file}")

    output_file = build_output_path(input_file, args.output)
    generate_pdutypes(input_file, config_file, output_file)


if __name__ == "__main__":
    main()
