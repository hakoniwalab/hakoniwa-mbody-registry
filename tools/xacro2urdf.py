#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path


COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
ROS_FIND_PATTERN = re.compile(r"\$\(\s*find\s+([^)]+?)\s*\)")
INCLUDE_PATTERN = re.compile(r"<xacro:include\b[^>]*\bfilename\s*=\s*['\"]([^'\"]+)['\"]")


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def parse_mappings(raw_args: list[str]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for raw_arg in raw_args:
        if "=" not in raw_arg:
            fail(f"Invalid --arg '{raw_arg}'. Use NAME=VALUE format.")
        name, value = raw_arg.split("=", 1)
        if not name.strip():
            fail(f"Invalid --arg '{raw_arg}'. Argument name must not be empty.")
        mappings[name.strip()] = value
    return mappings


def strip_xml_comments(text: str) -> str:
    return COMMENT_PATTERN.sub("", text)


def find_ros_find_usages(text: str) -> list[tuple[int, str]]:
    matches: list[tuple[int, str]] = []
    for match in ROS_FIND_PATTERN.finditer(strip_xml_comments(text)):
        line_number = text[: match.start()].count("\n") + 1
        matches.append((line_number, match.group(0)))
    return matches


def resolve_include_path(base_file: Path, include_filename: str) -> Path | None:
    if "$(" in include_filename or "${" in include_filename:
        return None
    candidate = (base_file.parent / include_filename).resolve()
    return candidate if candidate.is_file() else None


def scan_for_ros_find(start_file: Path) -> list[tuple[Path, int, str]]:
    queue = [start_file.resolve()]
    visited: set[Path] = set()
    findings: list[tuple[Path, int, str]] = []

    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)

        text = current.read_text(encoding="utf-8")
        for line_number, expression in find_ros_find_usages(text):
            findings.append((current, line_number, expression))

        stripped = strip_xml_comments(text)
        for include_match in INCLUDE_PATTERN.finditer(stripped):
            include_path = resolve_include_path(current, include_match.group(1))
            if include_path is not None and include_path not in visited:
                queue.append(include_path)

    return findings


def import_xacro_module():
    try:
        import xacro
    except ModuleNotFoundError:
        fail("'xacro' Python package not found. Install it with: pip install xacro")
    return xacro


def build_output_path(input_file: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)
    if input_file.suffix == ".urdf":
        return input_file.with_name(f"{input_file.stem}.generated.urdf")
    return input_file.with_suffix(".urdf")


def convert_xacro_to_urdf(input_file: Path, output_file: Path, mappings: dict[str, str]) -> None:
    ros_find_usages = scan_for_ros_find(input_file)
    if ros_find_usages:
        details = "\n".join(
            f"  - {path}:{line_number}: {expression}"
            for path, line_number, expression in ros_find_usages
        )
        fail(
            "Detected ROS-style '$(find ...)' expressions, which are not supported in this ROS-free tool.\n"
            "Replace them with relative paths or pre-fetched local paths before conversion:\n"
            f"{details}"
        )

    xacro = import_xacro_module()

    print(f"Converting {input_file} -> {output_file}")
    if mappings:
        print(f"  - xacro args: {mappings}")

    try:
        document = xacro.process_file(str(input_file), mappings=mappings)
    except Exception as exc:
        fail(f"xacro processing failed: {exc}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(document.toprettyxml(indent="  "), encoding="utf-8")
    print(f"Successfully wrote {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a xacro-based robot description into a plain URDF without ROS."
    )
    parser.add_argument("input", help="Path to the input .xacro file or xacro-enabled .urdf file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output .urdf file. Defaults to INPUT.urdf, or INPUT.generated.urdf when INPUT already ends with .urdf.",
    )
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Set a xacro argument. Repeat for multiple values.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    mappings = parse_mappings(args.arg)
    output_file = build_output_path(input_file, args.output)
    convert_xacro_to_urdf(input_file, output_file, mappings)


if __name__ == "__main__":
    main()
