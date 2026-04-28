from __future__ import annotations

import numpy as np


DEBUG_COLOR_TABLE = [
    ("scan", np.asarray([0.95, 0.8, 0.15, 1.0], dtype=float)),
    ("sensor", np.asarray([0.95, 0.8, 0.15, 1.0], dtype=float)),
    ("base", np.asarray([0.85, 0.2, 0.2, 1.0], dtype=float)),
    ("left", np.asarray([0.2, 0.7, 0.25, 1.0], dtype=float)),
    ("right", np.asarray([0.2, 0.35, 0.85, 1.0], dtype=float)),
    ("caster", np.asarray([0.7, 0.2, 0.8, 1.0], dtype=float)),
]
DEBUG_COLOR_FALLBACK = np.asarray([0.9, 0.45, 0.1, 1.0], dtype=float)


def rgba_to_uchar(rgba: np.ndarray) -> np.ndarray:
    return np.clip(np.round(rgba * 255), 0, 255).astype(np.uint8)


def debug_rgba_for_name(name: str) -> np.ndarray:
    lowered = name.lower()
    for token, rgba in DEBUG_COLOR_TABLE:
        if token in lowered:
            return rgba
    return DEBUG_COLOR_FALLBACK


def strip_mesh_metadata(mesh) -> None:
    mesh.metadata.clear()


def apply_material_rgba(trimesh, mesh, rgba: np.ndarray | None) -> None:
    if rgba is None:
        return

    mesh.visual.material = trimesh.visual.material.PBRMaterial(
        baseColorFactor=rgba_to_uchar(rgba),
        metallicFactor=0.0,
        roughnessFactor=0.9,
    )
    mesh.visual.vertex_colors = None
    mesh.visual.face_colors = None

