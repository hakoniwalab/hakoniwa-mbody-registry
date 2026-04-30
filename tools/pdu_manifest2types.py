#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import json
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
        return input_file.with_name("pdutypes.json")
    return generated_dir / "pdutypes.json"


def load_manifest(manifest_file: Path) -> dict:
    with manifest_file.open("r", encoding="utf-8") as file_obj:
        manifest = yaml.safe_load(file_obj)

    if not isinstance(manifest, dict):
        fail("Manifest root must be a mapping.")
    if manifest.get("format") != "hako_pdu_manifest":
        fail("Manifest 'format' must be 'hako_pdu_manifest'.")
    if not isinstance(manifest.get("robot_name"), str) or not manifest["robot_name"].strip():
        fail("Manifest must define a non-empty 'robot_name'.")

    bodies = manifest.get("bodies", {})
    sensors = manifest.get("sensors", [])
    extras = manifest.get("extras", [])
    if not isinstance(bodies, dict):
        fail("'bodies' must be a mapping.")
    if not isinstance(sensors, list):
        fail("'sensors' must be a list.")
    if not isinstance(extras, list):
        fail("'extras' must be a list.")
    if not bodies and not sensors and not extras:
        fail("Manifest must contain at least one entry in bodies, sensors, or extras.")

    return manifest


def load_size_registry() -> dict[str, int]:
    try:
        module = importlib.import_module("hakoniwa_pdu.pdu_msgs.pdu_size")
        registry = getattr(module, "PDU_SIZE", None)
        if isinstance(registry, dict):
            return dict(registry)
    except ImportError:
        pass

    fallback = (
        Path(__file__).resolve().parents[2]
        / "hakoniwa-pdu-python"
        / "src"
        / "hakoniwa_pdu"
        / "pdu_msgs"
        / "pdu_size.py"
    )
    if not fallback.is_file():
        return {}

    namespace: dict[str, object] = {}
    exec(fallback.read_text(encoding="utf-8"), namespace)
    registry = namespace.get("PDU_SIZE")
    return dict(registry) if isinstance(registry, dict) else {}


def require_string(entry: dict, key: str, context: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{context} must define a non-empty '{key}'.")
    return value


def require_int(entry: dict, key: str, context: str) -> int:
    value = entry.get(key)
    if not isinstance(value, int):
        fail(f"{context} must define an integer '{key}'.")
    return value


def resolve_pdu_size(entry: dict, registry: dict[str, int], context: str) -> int | None:
    value = entry.get("pdu_size")
    if value == "auto" or value is None:
        pdu_type = require_string(entry, "pdu_type", context)
        return registry.get(pdu_type)
    if isinstance(value, int):
        return value
    fail(f"{context} has invalid 'pdu_size'. Expected integer, null, or 'auto'.")
    return None


def collect_entries(manifest: dict) -> list[dict]:
    entries: list[dict] = []
    bodies = manifest.get("bodies", {})

    base = bodies.get("base")
    if base is not None:
        if not isinstance(base, dict):
            fail("'bodies.base' must be a mapping.")
        entries.append({"section": "bodies.base", **base})

    joints = bodies.get("joints")
    if joints is not None:
        if not isinstance(joints, dict):
            fail("'bodies.joints' must be a mapping.")
        entries.append({"section": "bodies.joints", **joints})

    for index, sensor in enumerate(manifest.get("sensors", [])):
        if not isinstance(sensor, dict):
            fail(f"'sensors[{index}]' must be a mapping.")
        entries.append({"section": f"sensors[{index}]", **sensor})

    for index, extra in enumerate(manifest.get("extras", [])):
        if not isinstance(extra, dict):
            fail(f"'extras[{index}]' must be a mapping.")
        entries.append({"section": f"extras[{index}]", **extra})

    return entries


def generate_pdutypes(manifest_file: Path, output_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    registry = load_size_registry()
    entries = collect_entries(manifest)

    pdutypes: list[dict] = []
    used_channel_ids: set[int] = set()
    used_names: set[str] = set()

    for entry in entries:
        context = entry["section"]
        channel_id = require_int(entry, "channel_id", context)
        name = require_string(entry, "pdu_name", context)
        pdu_type = require_string(entry, "pdu_type", context)
        pdu_size = resolve_pdu_size(entry, registry, context)

        if pdu_size is None:
            fail(f"{context} could not resolve 'pdu_size' for type '{pdu_type}'.")
        if channel_id in used_channel_ids:
            fail(f"Duplicate channel_id detected: {channel_id}")
        if name in used_names:
            fail(f"Duplicate PDU name detected: {name}")

        used_channel_ids.add(channel_id)
        used_names.add(name)
        pdutypes.append(
            {
                "channel_id": channel_id,
                "pdu_size": pdu_size,
                "name": name,
                "type": pdu_type,
            }
        )

    pdutypes.sort(key=lambda item: item["channel_id"])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(pdutypes, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_file} with {len(pdutypes)} PDU entries")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Hakoniwa pdutypes.json from a pdu-manifest.yaml file."
    )
    parser.add_argument("input", help="Path to the input pdu-manifest.yaml file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output pdutypes.json file. Defaults to bodies/{name}/generated/pdutypes.json when the input is under bodies/{name}/.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    output_file = build_output_path(input_file, args.output)
    generate_pdutypes(input_file, output_file)


if __name__ == "__main__":
    main()
