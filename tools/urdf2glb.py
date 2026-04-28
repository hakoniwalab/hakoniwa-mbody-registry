#!/usr/bin/env python3

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from glb_material_utils import apply_material_rgba, debug_rgba_for_name, strip_mesh_metadata
from path_utils import default_generated_file, discover_package_dir


PACKAGE_URI_PATTERN = re.compile(r"^package://([^/]+)/(.+)$")


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def import_trimesh_module():
    try:
        import trimesh
    except ModuleNotFoundError:
        fail("'trimesh' Python package not found. Install it with: python3 -m pip install trimesh")
    return trimesh


@dataclass
class Joint:
    parent: str
    child: str
    transform: np.ndarray


@dataclass
class Visual:
    name: str
    geometry_type: str
    params: dict
    transform: np.ndarray
    material_rgba: np.ndarray | None


def parse_package_roots(raw_args: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for raw_arg in raw_args:
        if "=" not in raw_arg:
            fail(f"Invalid --package-root '{raw_arg}'. Use PACKAGE=PATH format.")
        package_name, raw_path = raw_arg.split("=", 1)
        package_name = package_name.strip()
        if not package_name:
            fail(f"Invalid --package-root '{raw_arg}'. Package name must not be empty.")
        package_path = Path(raw_path).expanduser().resolve()
        if not package_path.is_dir():
            fail(f"Package root for '{package_name}' does not exist: {package_path}")
        roots[package_name] = package_path
    return roots


def build_output_path(input_file: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg)
    return default_generated_file(input_file, ".glb")


def parse_xyz(value: str | None, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> np.ndarray:
    if not value:
        return np.asarray(default, dtype=float)
    parts = [float(part) for part in value.split()]
    if len(parts) != 3:
        fail(f"Expected 3 values, got '{value}'")
    return np.asarray(parts, dtype=float)


def rpy_to_matrix(rpy: np.ndarray) -> np.ndarray:
    roll, pitch, yaw = rpy
    cx, cy, cz = math.cos(roll), math.cos(pitch), math.cos(yaw)
    sx, sy, sz = math.sin(roll), math.sin(pitch), math.sin(yaw)

    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rz @ ry @ rx


def origin_to_transform(origin: ET.Element | None) -> np.ndarray:
    transform = np.eye(4)
    if origin is None:
        return transform
    xyz = parse_xyz(origin.get("xyz"))
    rpy = parse_xyz(origin.get("rpy"))
    transform[:3, :3] = rpy_to_matrix(rpy)
    transform[:3, 3] = xyz
    return transform


def discover_package_root(package_name: str, input_file: Path, explicit_roots: dict[str, Path]) -> Path | None:
    if package_name in explicit_roots:
        return explicit_roots[package_name]

    registry_match = discover_package_dir(input_file, package_name)
    if registry_match is not None:
        return registry_match

    resolved_input = input_file.resolve()
    for parent in resolved_input.parents:
        if parent.name == package_name:
            return parent
    return None


def resolve_mesh_path(filename: str, input_file: Path, explicit_roots: dict[str, Path]) -> Path:
    package_match = PACKAGE_URI_PATTERN.match(filename)
    if package_match:
        package_name, relative_resource = package_match.groups()
        package_root = discover_package_root(package_name, input_file, explicit_roots)
        if package_root is None:
            fail(
                f"Could not resolve package URI '{filename}'. "
                f"Pass --package-root {package_name}=PATH or place the URDF under a directory named '{package_name}'."
            )
        resolved = package_root / relative_resource
    else:
        resolved = (input_file.parent / filename).resolve()

    if not resolved.exists():
        fail(f"Mesh file not found: {resolved}")
    return resolved


def parse_materials(root: ET.Element) -> dict[str, np.ndarray]:
    materials: dict[str, np.ndarray] = {}
    for material in root.findall("material"):
        name = material.get("name")
        color = material.find("color")
        if name and color is not None and color.get("rgba"):
            rgba = np.asarray([float(part) for part in color.get("rgba").split()], dtype=float)
            if rgba.size == 4:
                materials[name] = rgba
    return materials


def extract_visual(link_name: str, index: int, visual_el: ET.Element, materials: dict[str, np.ndarray]) -> Visual | None:
    geometry = visual_el.find("geometry")
    if geometry is None:
        return None

    transform = origin_to_transform(visual_el.find("origin"))
    material_rgba = None
    material = visual_el.find("material")
    if material is not None:
        color = material.find("color")
        if color is not None and color.get("rgba"):
            material_rgba = np.asarray([float(part) for part in color.get("rgba").split()], dtype=float)
        elif material.get("name") in materials:
            material_rgba = materials[material.get("name")]

    mesh_el = geometry.find("mesh")
    if mesh_el is not None:
        filename = mesh_el.get("filename")
        if not filename:
            fail(f"Mesh visual in link '{link_name}' is missing filename.")
        scale = parse_xyz(mesh_el.get("scale"), default=(1.0, 1.0, 1.0))
        return Visual(
            name=f"{link_name}_visual_{index}",
            geometry_type="mesh",
            params={"filename": filename, "scale": scale},
            transform=transform,
            material_rgba=material_rgba,
        )

    box_el = geometry.find("box")
    if box_el is not None:
        size = parse_xyz(box_el.get("size"))
        return Visual(
            name=f"{link_name}_visual_{index}",
            geometry_type="box",
            params={"size": size},
            transform=transform,
            material_rgba=material_rgba,
        )

    cylinder_el = geometry.find("cylinder")
    if cylinder_el is not None:
        return Visual(
            name=f"{link_name}_visual_{index}",
            geometry_type="cylinder",
            params={
                "radius": float(cylinder_el.get("radius", "0")),
                "length": float(cylinder_el.get("length", "0")),
            },
            transform=transform,
            material_rgba=material_rgba,
        )

    sphere_el = geometry.find("sphere")
    if sphere_el is not None:
        return Visual(
            name=f"{link_name}_visual_{index}",
            geometry_type="sphere",
            params={"radius": float(sphere_el.get("radius", "0"))},
            transform=transform,
            material_rgba=material_rgba,
        )

    return None


def parse_robot(input_file: Path) -> tuple[dict[str, list[Visual]], dict[str, Joint], str]:
    tree = ET.parse(input_file)
    root = tree.getroot()
    materials = parse_materials(root)

    visuals_by_link: dict[str, list[Visual]] = {}
    child_links: set[str] = set()

    for link in root.findall("link"):
        link_name = link.get("name")
        if not link_name:
            fail("Encountered a link without a name.")
        visuals = []
        for index, visual_el in enumerate(link.findall("visual")):
            visual = extract_visual(link_name, index, visual_el, materials)
            if visual is not None:
                visuals.append(visual)
        visuals_by_link[link_name] = visuals

    joints: dict[str, Joint] = {}
    for joint_el in root.findall("joint"):
        parent_el = joint_el.find("parent")
        child_el = joint_el.find("child")
        if parent_el is None or child_el is None:
            continue
        parent = parent_el.get("link")
        child = child_el.get("link")
        if not parent or not child:
            continue
        child_links.add(child)
        joints[child] = Joint(parent=parent, child=child, transform=origin_to_transform(joint_el.find("origin")))

    link_names = set(visuals_by_link.keys())
    roots = sorted(link_names - child_links)
    if len(roots) != 1:
        fail(f"Expected exactly one root link, found: {roots}")

    return visuals_by_link, joints, roots[0]


def build_link_transforms(root_link: str, joints: dict[str, Joint]) -> dict[str, np.ndarray]:
    transforms = {root_link: np.eye(4)}
    pending = dict(joints)

    while pending:
        progressed = False
        for child, joint in list(pending.items()):
            if joint.parent not in transforms:
                continue
            transforms[child] = transforms[joint.parent] @ joint.transform
            del pending[child]
            progressed = True
        if not progressed:
            fail(f"Could not resolve joint tree for links: {sorted(pending.keys())}")

    return transforms


def create_geometry(
    trimesh,
    visual: Visual,
    input_file: Path,
    explicit_roots: dict[str, Path],
    debug_colors: bool,
):
    color_rgba = debug_rgba_for_name(visual.name) if debug_colors else visual.material_rgba

    if visual.geometry_type == "mesh":
        mesh_path = resolve_mesh_path(visual.params["filename"], input_file, explicit_roots)
        loaded = trimesh.load(mesh_path, force="scene")
        scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
        scale = visual.params["scale"]
        if not np.allclose(scale, np.ones(3)):
            scale_matrix = np.eye(4)
            scale_matrix[0, 0], scale_matrix[1, 1], scale_matrix[2, 2] = scale
            scene.apply_transform(scale_matrix)
        mesh = scene.to_mesh()
        strip_mesh_metadata(mesh)
        if color_rgba is not None:
            apply_material_rgba(trimesh, mesh, color_rgba)
        return mesh

    if visual.geometry_type == "box":
        mesh = trimesh.creation.box(extents=visual.params["size"])
        apply_material_rgba(trimesh, mesh, color_rgba)
        return mesh

    if visual.geometry_type == "cylinder":
        mesh = trimesh.creation.cylinder(
            radius=visual.params["radius"],
            height=visual.params["length"],
        )
        apply_material_rgba(trimesh, mesh, color_rgba)
        return mesh

    if visual.geometry_type == "sphere":
        mesh = trimesh.creation.icosphere(radius=visual.params["radius"])
        apply_material_rgba(trimesh, mesh, color_rgba)
        return mesh

    fail(f"Unsupported visual geometry type: {visual.geometry_type}")


def convert_urdf_to_glb(
    input_file: Path,
    output_file: Path,
    explicit_roots: dict[str, Path],
    debug_colors: bool,
) -> None:
    """
    Export the entire robot as one GLB scene.

    This mode preserves the existing behavior:
      visual transform = root_to_link_transform @ visual_origin_transform

    Therefore every link mesh is baked into the root-link/world-like robot frame.
    This is good for a standalone complete robot GLB, but not suitable for
    per-link viewer animation because movable parts already include their mount
    offsets in the vertex data.
    """
    trimesh = import_trimesh_module()
    visuals_by_link, joints, root_link = parse_robot(input_file)
    link_transforms = build_link_transforms(root_link, joints)

    scene = trimesh.Scene(base_frame=root_link)
    for link_name, visuals in visuals_by_link.items():
        link_transform = link_transforms.get(link_name, np.eye(4))
        for visual in visuals:
            geometry = create_geometry(trimesh, visual, input_file, explicit_roots, debug_colors)
            transform = link_transform @ visual.transform
            scene.add_geometry(geometry, node_name=visual.name, transform=transform)

    if not scene.geometry:
        fail("No visual geometry found in the URDF.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    glb_bytes = scene.export(file_type="glb")
    output_file.write_bytes(glb_bytes)
    print(f"Successfully wrote {output_file}")


def convert_urdf_to_link_local_glbs(
    input_file: Path,
    output_dir: Path,
    explicit_roots: dict[str, Path],
    debug_colors: bool,
) -> None:
    """
    Export one GLB per URDF link in link-local coordinates.

    This mode is intended for Hakoniwa Viewer Model / Godot scene generation.

    Important rule:
      visual transform = visual_origin_transform

    The root_to_link transform is intentionally NOT applied. As a result:
      - wheel_left_link.glb is centered in the wheel_left_link frame.
      - wheel_right_link.glb is centered in the wheel_right_link frame.
      - base_scan.glb is centered in the base_scan frame.
      - The viewer applies MJCF/ViewerModel mount transforms later.

    This avoids double-applying link placement in Godot or other viewers.
    """
    trimesh = import_trimesh_module()
    visuals_by_link, _joints, _root_link = parse_robot(input_file)

    output_dir.mkdir(parents=True, exist_ok=True)

    wrote_any = False
    for link_name, visuals in visuals_by_link.items():
        if not visuals:
            continue

        scene = trimesh.Scene(base_frame=link_name)

        for visual in visuals:
            geometry = create_geometry(trimesh, visual, input_file, explicit_roots, debug_colors)

            # Link-local export:
            # Do not apply root_to_link transform here.
            # Only apply the visual origin defined inside the link frame.
            transform = visual.transform

            scene.add_geometry(
                geometry,
                node_name=visual.name,
                transform=transform,
            )

        if not scene.geometry:
            continue

        output_file = output_dir / f"{link_name}.glb"
        glb_bytes = scene.export(file_type="glb")
        output_file.write_bytes(glb_bytes)
        wrote_any = True
        print(f"Successfully wrote {output_file}")

    if not wrote_any:
        fail("No visual geometry found in the URDF.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a URDF file into GLB. "
            "By default, exports one complete robot GLB. "
            "With --parts-dir, exports one link-local GLB per URDF link."
        )
    )
    parser.add_argument("input", help="Path to the input URDF file.")
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Path to the output complete GLB file. "
            "Defaults to bodies/{name}/generated/{stem}.glb when the input is under bodies/{name}/. "
            "Ignored when --parts-dir is specified."
        ),
    )
    parser.add_argument(
        "--parts-dir",
        help=(
            "Output per-link GLB files into this directory. "
            "Each GLB is exported in link-local coordinates and is suitable for viewer model based scene generation."
        ),
    )
    parser.add_argument(
        "--package-root",
        action="append",
        default=[],
        metavar="PACKAGE=PATH",
        help="Resolve package://PACKAGE/... URIs against PATH. Repeat for multiple packages.",
    )
    parser.add_argument(
        "--debug-colors",
        action="store_true",
        help="Override source colors with high-contrast debug materials to verify viewer import behavior.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.is_file():
        fail(f"Input file not found at {input_file}")

    package_roots = parse_package_roots(args.package_root)

    if args.parts_dir:
        parts_dir = Path(args.parts_dir)
        print(f"Converting {input_file} -> {parts_dir}/<link_name>.glb")
        convert_urdf_to_link_local_glbs(input_file, parts_dir, package_roots, args.debug_colors)
        return

    output_file = build_output_path(input_file, args.output)
    print(f"Converting {input_file} -> {output_file}")
    convert_urdf_to_glb(input_file, output_file, package_roots, args.debug_colors)


if __name__ == "__main__":
    main()
