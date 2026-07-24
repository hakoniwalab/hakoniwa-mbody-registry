#!/usr/bin/env python3

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def resolve_relative(base_xml: Path, directory: str, file_name: str) -> Path:
    base_dir = base_xml.parent
    if directory:
        base_dir = base_dir / directory
    return (base_dir / file_name).resolve()


def validate_xml(xml_path: Path, visited: set[Path]) -> list[str]:
    xml_path = xml_path.resolve()
    if xml_path in visited:
        return []
    visited.add(xml_path)

    if not xml_path.is_file():
        return [f"missing XML: {xml_path}"]

    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        return [f"invalid XML {xml_path}: {exc}"]

    errors: list[str] = []

    compiler = root.find("compiler")
    meshdir = compiler.get("meshdir", "") if compiler is not None else ""

    for include in root.iter("include"):
        file_name = include.get("file")
        if not file_name:
            continue
        include_path = resolve_relative(xml_path, "", file_name)
        if not include_path.is_file():
            errors.append(f"{xml_path}: include not found: {file_name}")
            continue
        errors.extend(validate_xml(include_path, visited))

    for mesh in root.iter("mesh"):
        file_name = mesh.get("file")
        if not file_name:
            continue
        mesh_path = resolve_relative(xml_path, meshdir, file_name)
        if not mesh_path.is_file():
            errors.append(
                f"{xml_path}: mesh not found: {file_name} "
                f"(meshdir={meshdir or '.'})"
            )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate local file references needed by a materialized MJCF model."
    )
    parser.add_argument("entry_mjcf", type=Path)
    args = parser.parse_args()

    entry = args.entry_mjcf.resolve()
    errors = validate_xml(entry, set())
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)

    print(f"MJCF assets valid: {entry}")


if __name__ == "__main__":
    main()
