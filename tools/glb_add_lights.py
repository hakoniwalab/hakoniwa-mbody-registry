#!/usr/bin/env python3
"""Make a body's lights shine in its parts GLB: glowing materials and lamps.

    python tools/glb_add_lights.py <parts dir> <lights.yaml>

lights.yaml (a body's config/lights.yaml):

    glow:              # materials of this base colour (the geoms' rgba) glow
      - {rgba: [0.25, 0.65, 1.0], emissive: [0.2, 0.6, 1.0], strength: 2.0}
    lights:            # lamps (KHR_lights_punctual) on a part, in its body frame
      - {part: vehicle, type: spot, position: [1.1, 0.4, 0.2], direction: [1, 0, 0],
         color: [1.0, 0.95, 0.85], intensity: 40, range: 25, inner_cone_deg: 12, outer_cone_deg: 32}

The parts are the GLBs mjcf2glb.py writes (one per body, in the MJCF frame);
only their JSON changes. A viewer shows the glow (KHR_materials_emissive_
strength) and lights its surroundings with the lamps, which move with the
part.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import yaml

LIGHTS = "KHR_lights_punctual"
STRENGTH = "KHR_materials_emissive_strength"
DIGITS = 6  # decimals of computed angles and rotations


class LightsError(ValueError):
    pass


def read_glb(data: bytes) -> tuple[dict, bytes]:
    magic, version, _length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise LightsError("not a glTF 2.0 binary")
    json_length, _ = struct.unpack_from("<II", data, 12)
    document = json.loads(data[20:20 + json_length])
    rest = 20 + json_length
    binary = b""
    if rest + 8 <= len(data):
        bin_length, _ = struct.unpack_from("<II", data, rest)
        binary = data[rest + 8:rest + 8 + bin_length]
    return document, binary


def write_glb(document: dict, binary: bytes) -> bytes:
    text = json.dumps(document, separators=(",", ":")).encode("utf-8")
    text += b" " * (-len(text) % 4)
    binary = binary + b"\0" * (-len(binary) % 4)
    chunks = struct.pack("<II", len(text), 0x4E4F534A) + text
    if binary:
        chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
    return struct.pack("<III", 0x46546C67, 2, 12 + len(chunks)) + chunks


def use(document: dict, extension: str) -> None:
    used = document.setdefault("extensionsUsed", [])
    if extension not in used:
        used.append(extension)


def glow(document: dict, rules: list[dict]) -> int:
    """Materials whose base colour matches a rule's rgba get its emission."""
    count = 0
    for material in document.get("materials", []):
        base = material.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
        for rule in rules:
            want = rule["rgba"]
            if all(abs(base[i] - want[i]) < 0.02 for i in range(3)):
                material["emissiveFactor"] = [float(v) for v in rule.get("emissive", want[:3])]
                strength = float(rule.get("strength", 1.0))
                if strength != 1.0:
                    material.setdefault("extensions", {})[STRENGTH] = {"emissiveStrength": strength}
                    use(document, STRENGTH)
                count += 1
                break
    return count


def rotation_to(direction) -> list[float]:
    """A quaternion (x, y, z, w) turning glTF's light axis (-Z) onto direction."""
    x, y, z = (float(v) for v in direction)
    norm = math.sqrt(x * x + y * y + z * z)
    if norm == 0:
        raise LightsError("a light's direction must not be zero")
    x, y, z = x / norm, y / norm, z / norm
    # From (0, 0, -1) to (x, y, z): axis = cross, angle = acos(dot).
    dot = -z
    if dot > 0.999999:
        return [0.0, 0.0, 0.0, 1.0]
    if dot < -0.999999:
        return [0.0, 1.0, 0.0, 0.0]
    axis = (y, -x, 0.0)  # (0,0,-1) x (x,y,z)
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2)
    half = math.acos(max(-1.0, min(1.0, dot))) / 2
    s = math.sin(half) / length
    # Rounded: libm's last digits differ between platforms, and the GLB must
    # come out byte for byte the same everywhere (forge.py --verify).
    return [round(axis[0] * s, DIGITS), round(axis[1] * s, DIGITS), 0.0, round(math.cos(half), DIGITS)]


def add_lights(document: dict, lights: list[dict]) -> None:
    store = document.setdefault("extensions", {}).setdefault(LIGHTS, {"lights": []})
    use(document, LIGHTS)
    scene = document.setdefault("scenes", [{"nodes": []}])[document.get("scene", 0)]
    for light in lights:
        entry = {"type": light.get("type", "point"), "color": [float(v) for v in light.get("color", [1, 1, 1])],
                 "intensity": float(light.get("intensity", 10.0))}
        if "range" in light:
            entry["range"] = float(light["range"])
        node = {"name": light.get("name", f"light_{len(store['lights'])}"),
                "translation": [float(v) for v in light["position"]]}
        if entry["type"] == "spot":
            entry["spot"] = {"innerConeAngle": round(math.radians(float(light.get("inner_cone_deg", 15))), DIGITS),
                             "outerConeAngle": round(math.radians(float(light.get("outer_cone_deg", 35))), DIGITS)}
            node["rotation"] = rotation_to(light.get("direction", [1, 0, 0]))
        store["lights"].append(entry)
        node["extensions"] = {LIGHTS: {"light": len(store["lights"]) - 1}}
        document.setdefault("nodes", []).append(node)
        scene.setdefault("nodes", []).append(len(document["nodes"]) - 1)


def apply(parts_dir: Path, config: dict) -> dict:
    rules = config.get("glow", []) or []
    by_part: dict[str, list] = {}
    for light in config.get("lights", []) or []:
        by_part.setdefault(light["part"], []).append(light)
    report = {}
    for path in sorted(parts_dir.glob("*.glb")):
        document, binary = read_glb(path.read_bytes())
        glowing = glow(document, rules)
        lamps = by_part.pop(path.stem, [])
        if lamps:
            add_lights(document, lamps)
        if glowing or lamps:
            path.write_bytes(write_glb(document, binary))
            report[path.name] = {"glowing_materials": glowing, "lights": len(lamps)}
    if by_part:
        raise LightsError(f"no parts GLB for lights on {sorted(by_part)}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("parts_dir", type=Path)
    parser.add_argument("lights", type=Path)
    args = parser.parse_args()
    try:
        report = apply(args.parts_dir, yaml.safe_load(args.lights.read_text(encoding="utf-8")) or {})
    except (LightsError, KeyError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
