#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


REPLACEMENTS = {
    "$(find tracer_description)/urdf/": "",
    "package://tracer_description/": "../",
    '    <xacro:include filename="tracer.gazebo" />\n': "",
}


def adapt_xacro_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = original
    for old, new in REPLACEMENTS.items():
        updated = updated.replace(old, new)

    if updated == original:
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Adapt AgileX Tracer ROS xacro includes for ROS-free MBody conversion."
    )
    parser.add_argument(
        "source_root",
        type=Path,
        help="Fetched source root containing tracer_description/.",
    )
    args = parser.parse_args()

    urdf_dir = args.source_root / "tracer_description" / "urdf"
    if not urdf_dir.is_dir():
        raise SystemExit(f"URDF directory not found: {urdf_dir}")

    changed = []
    for path in sorted(urdf_dir.glob("*")):
        if path.suffix not in {".xacro", ".gazebo"}:
            continue
        if adapt_xacro_file(path):
            changed.append(path)

    print(f"Adapted {len(changed)} AgileX Tracer xacro/gazebo file(s).")
    for path in changed:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
