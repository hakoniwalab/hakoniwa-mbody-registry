#!/usr/bin/env python3

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from path_utils import default_generated_parts_dir


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def import_trimesh_module():
    try:
        import trimesh
    except ModuleNotFoundError:
        fail("'trimesh' Python package not found. Install it with: python3 -m pip install trimesh")
    return trimesh


def sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return sanitized or "part"


def parse_vec(value: str | None, expected: int, default: list[float]) -> np.ndarray:
    if not value:
        return np.asarray(default, dtype=float)
    parts = [float(part) for part in value.split()]
    if len(parts) != expected:
        fail(f"Expected {expected} values, got '{value}'")
    return np.asarray(parts, dtype=float)


def quat_to_matrix(quat: np.ndarray) -> np.ndarray:
    w, x, y, z = quat
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm == 0:
        return np.eye(3)
    w, x, y, z = quat / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def pose_to_transform(pos: str | None, quat: str | None) -> np.ndarray:
    transform = np.eye(4)
    transform[:3, 3] = parse_vec(pos, 3, [0.0, 0.0, 0.0])
    transform[:3, :3] = quat_to_matrix(parse_vec(quat, 4, [1.0, 0.0, 0.0, 0.0]))
    return transform


@dataclass
class MeshAsset:
    file: Path
    scale: np.ndarray


@dataclass
class GeomSpec:
    name: str
    geometry_type: str
    params: dict
    transform: np.ndarray
    rgba: np.ndarray | None


def parse_mesh_assets(root: ET.Element) -> dict[str, MeshAsset]:
    assets: dict[str, MeshAsset] = {}
    asset_element = root.find("asset")
    if asset_element is None:
        return assets

    for mesh in asset_element.findall("mesh"):
        name = mesh.get("name")
        file_path = mesh.get("file")
        if not name or not file_path:
            continue
        resolved = Path(file_path).expanduser().resolve()
        if not resolved.exists():
            fail(f"MJCF mesh asset not found: {resolved}")
        assets[name] = MeshAsset(
            file=resolved,
            scale=parse_vec(mesh.get("scale"), 3, [1.0, 1.0, 1.0]),
        )
    return assets


def parse_rgba(value: str | None) -> np.ndarray | None:
    if not value:
        return None
    rgba = parse_vec(value, 4, [0.5, 0.5, 0.5, 1.0])
    return rgba


def parse_geom(geom: ET.Element, index: int, body_name: str, mesh_assets: dict[str, MeshAsset]) -> GeomSpec | None:
    geom_type = geom.get("type", "sphere")
    name = geom.get("name") or f"{body_name}_geom_{index}"
    transform = pose_to_transform(geom.get("pos"), geom.get("quat"))
    rgba = parse_rgba(geom.get("rgba"))

    if geom_type == "mesh":
        mesh_name = geom.get("mesh")
        if not mesh_name:
            fail(f"Mesh geom '{name}' is missing mesh attribute.")
        asset = mesh_assets.get(mesh_name)
        if asset is None:
            fail(f"Mesh geom '{name}' references unknown asset '{mesh_name}'.")
        return GeomSpec(
            name=name,
            geometry_type="mesh",
            params={"file": asset.file, "scale": asset.scale},
            transform=transform,
            rgba=rgba,
        )

    if geom_type == "box":
        size = parse_vec(geom.get("size"), 3, [0.5, 0.5, 0.5])
        return GeomSpec(name=name, geometry_type="box", params={"size": size}, transform=transform, rgba=rgba)

    if geom_type == "cylinder":
        size = parse_vec(geom.get("size"), 2, [0.5, 0.5])
        return GeomSpec(
            name=name,
            geometry_type="cylinder",
            params={"radius": size[0], "half_length": size[1]},
            transform=transform,
            rgba=rgba,
        )

    if geom_type == "sphere":
        size = parse_vec(geom.get("size"), 1, [0.5])
        return GeomSpec(name=name, geometry_type="sphere", params={"radius": size[0]}, transform=transform, rgba=rgba)

    print(f"Warning: skipping unsupported geom type '{geom_type}' in '{name}'", file=sys.stderr)
    return None


def apply_rgba(mesh, rgba: np.ndarray | None):
    if rgba is None:
        return
    color = np.clip(np.round(rgba * 255), 0, 255).astype(np.uint8)
    mesh.visual.face_colors = color


def create_geometry(trimesh, geom: GeomSpec):
    if geom.geometry_type == "mesh":
        loaded = trimesh.load(geom.params["file"], force="scene")
        scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
        scale = geom.params["scale"]
        if not np.allclose(scale, np.ones(3)):
            scale_matrix = np.eye(4)
            scale_matrix[0, 0], scale_matrix[1, 1], scale_matrix[2, 2] = scale
            scene.apply_transform(scale_matrix)
        mesh = scene.to_mesh()
        apply_rgba(mesh, geom.rgba)
        return mesh

    if geom.geometry_type == "box":
        mesh = trimesh.creation.box(extents=geom.params["size"] * 2.0)
        apply_rgba(mesh, geom.rgba)
        return mesh

    if geom.geometry_type == "cylinder":
        mesh = trimesh.creation.cylinder(
            radius=geom.params["radius"],
            height=geom.params["half_length"] * 2.0,
        )
        apply_rgba(mesh, geom.rgba)
        return mesh

    if geom.geometry_type == "sphere":
        mesh = trimesh.creation.icosphere(radius=geom.params["radius"])
        apply_rgba(mesh, geom.rgba)
        return mesh

    fail(f"Unsupported geom type: {geom.geometry_type}")


def collect_body_parts(
    body: ET.Element,
    parent_transform: np.ndarray,
    mesh_assets: dict[str, MeshAsset],
    parts: dict[str, list[tuple[GeomSpec, np.ndarray]]],
) -> None:
    body_name = body.get("name", "worldbody")
    world_transform = parent_transform @ pose_to_transform(body.get("pos"), body.get("quat"))

    direct_geoms: list[tuple[GeomSpec, np.ndarray]] = []
    for index, geom in enumerate(body.findall("geom")):
        spec = parse_geom(geom, index, body_name, mesh_assets)
        if spec is not None:
            direct_geoms.append((spec, world_transform @ spec.transform))

    if direct_geoms:
        parts[body_name] = direct_geoms

    for child in body.findall("body"):
        collect_body_parts(child, world_transform, mesh_assets, parts)


def collect_geom_parts(
    body: ET.Element,
    parent_transform: np.ndarray,
    mesh_assets: dict[str, MeshAsset],
    parts: dict[str, list[tuple[GeomSpec, np.ndarray]]],
) -> None:
    body_name = body.get("name", "worldbody")
    world_transform = parent_transform @ pose_to_transform(body.get("pos"), body.get("quat"))

    for index, geom in enumerate(body.findall("geom")):
        spec = parse_geom(geom, index, body_name, mesh_assets)
        if spec is not None:
            part_name = spec.name
            parts[part_name] = [(spec, world_transform @ spec.transform)]

    for child in body.findall("body"):
        collect_geom_parts(child, world_transform, mesh_assets, parts)


def export_parts(input_file: Path, output_dir: Path, split_by: str) -> None:
    trimesh = import_trimesh_module()

    root = ET.parse(input_file).getroot()
    worldbody = root.find("worldbody")
    if worldbody is None:
        fail("MJCF is missing <worldbody>.")

    mesh_assets = parse_mesh_assets(root)
    parts: dict[str, list[tuple[GeomSpec, np.ndarray]]] = {}

    if split_by == "body":
        collect_body_parts(worldbody, np.eye(4), mesh_assets, parts)
    elif split_by == "geom":
        collect_geom_parts(worldbody, np.eye(4), mesh_assets, parts)
    else:
        fail(f"Unsupported split mode: {split_by}")

    if not parts:
        fail("No exportable geoms found in the MJCF.")

    output_dir.mkdir(parents=True, exist_ok=True)
    for part_name, geoms in parts.items():
        scene = trimesh.Scene(base_frame="part")
        for geom, transform in geoms:
            geometry = create_geometry(trimesh, geom)
            scene.add_geometry(geometry, node_name=geom.name, transform=transform)
        output_path = output_dir / f"{sanitize_name(part_name)}.glb"
        output_path.write_bytes(scene.export(file_type="glb"))
        print(f"Wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split an MJCF XML model into per-body or per-geom GLB files."
    )
    parser.add_argument("input", help="Path to the input MJCF XML file.")
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory for generated GLB files. Defaults to bodies/{name}/generated/parts when the input is under bodies/{name}/.",
    )
    parser.add_argument(
        "--split-by",
        choices=["body", "geom"],
        default="body",
        help="Split GLB files by direct MJCF body geoms or by individual geoms. Default: body.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = default_generated_parts_dir(input_file)

    print(f"Splitting {input_file} -> {output_dir} ({args.split_by})")
    export_parts(input_file, output_dir, args.split_by)


if __name__ == "__main__":
    main()
