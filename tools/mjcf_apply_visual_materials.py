#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


class VisualMaterialError(ValueError):
    pass


def mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise VisualMaterialError(f"{label} must be a mapping")
    return value


def scalar(value, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise VisualMaterialError(f"{label} must be a string or number")
    return str(value)


def apply_visual_materials(input_file: Path, config_file: Path, output_file: Path) -> None:
    config = mapping(yaml.safe_load(config_file.read_text(encoding="utf-8")), "config")
    materials = mapping(config.get("materials"), "materials")
    assignments = mapping(config.get("mesh_assignments"), "mesh_assignments")

    tree = ET.parse(input_file)
    root = tree.getroot()
    asset = root.find("asset")
    if asset is None:
        asset = ET.Element("asset")
        root.insert(0, asset)

    for material_name, raw_attributes in materials.items():
        attributes = mapping(raw_attributes, f"materials.{material_name}")
        if asset.find(f"material[@name='{material_name}']") is not None:
            raise VisualMaterialError(f"duplicate material name: {material_name}")
        ET.SubElement(
            asset,
            "material",
            {"name": material_name, **{
                str(key): scalar(value, f"materials.{material_name}.{key}")
                for key, value in attributes.items()
            }},
        )

    mesh_names = {
        mesh.get("name") for mesh in asset.findall("mesh") if mesh.get("name")
    }
    unknown_meshes = sorted(set(assignments) - mesh_names)
    if unknown_meshes:
        raise VisualMaterialError(
            "mesh_assignments references unknown mesh(es): " + ", ".join(unknown_meshes)
        )

    assigned = 0
    for mesh_name, material_name_value in assignments.items():
        material_name = scalar(material_name_value, f"mesh_assignments.{mesh_name}")
        if material_name not in materials:
            raise VisualMaterialError(
                f"mesh_assignments.{mesh_name} references unknown material: {material_name}"
            )
        matches = root.findall(f".//geom[@mesh='{mesh_name}']")
        if not matches:
            raise VisualMaterialError(f"mesh has no geom assignment target: {mesh_name}")
        for geom in matches:
            geom.set("material", material_name)
            geom.attrib.pop("rgba", None)
            assigned += 1

    output_file.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(output_file, encoding="utf-8", xml_declaration=False)
    print(
        f"Applied visual materials from {config_file} -> {output_file} "
        f"(materials={len(materials)}, geom_assignments={assigned})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply explicit, recipe-owned materials to MJCF mesh geoms."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    args = parser.parse_args()
    try:
        apply_visual_materials(args.input, args.config, args.output)
    except (OSError, ET.ParseError, VisualMaterialError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
