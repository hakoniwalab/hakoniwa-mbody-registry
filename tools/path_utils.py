from __future__ import annotations

from pathlib import Path


def infer_robot_root(input_path: Path) -> tuple[Path, str] | None:
    resolved = input_path.resolve()
    for candidate in [resolved] + list(resolved.parents):
        if candidate.parent.name == "bodies":
            return candidate, candidate.name
    return None


def infer_generated_dir(input_path: Path) -> Path | None:
    inferred = infer_robot_root(input_path)
    if inferred is None:
        return None
    robot_root, _ = inferred
    return robot_root / "generated"


def infer_source_dir(input_path: Path) -> Path | None:
    inferred = infer_robot_root(input_path)
    if inferred is None:
        return None
    robot_root, _ = inferred
    return robot_root / "source"


def default_generated_file(input_path: Path, suffix: str) -> Path:
    generated_dir = infer_generated_dir(input_path)
    if generated_dir is None:
        return input_path.with_suffix(suffix)
    return generated_dir / f"{input_path.stem}{suffix}"


def default_generated_parts_dir(input_path: Path) -> Path:
    generated_dir = infer_generated_dir(input_path)
    if generated_dir is None:
        stem_dir = input_path.with_suffix("")
        return stem_dir.parent / f"{stem_dir.name}_parts"
    return generated_dir / "parts"


def discover_package_dir(input_path: Path, package_name: str) -> Path | None:
    source_dir = infer_source_dir(input_path)
    if source_dir is None or not source_dir.is_dir():
        return None

    direct = source_dir / package_name
    if direct.is_dir():
        return direct

    matches = sorted(
        candidate
        for candidate in source_dir.rglob(package_name)
        if candidate.is_dir() and candidate.name == package_name
    )
    return matches[0] if matches else None
