#!/usr/bin/env python3
"""Build the four colour variants of Hakoniwa Car 2: a lofted body mesh (body_mesh.py) and primitive details."""

from __future__ import annotations

from pathlib import Path

COLORS = {
    "default": "0.20 0.22 0.24 1",
    "white": "0.88 0.89 0.90 1",
    "red": "0.62 0.07 0.06 1",
    "blue": "0.08 0.22 0.48 1",
}
BLACK = "0.035 0.045 0.055 1"
GLASS = "0.10 0.16 0.19 0.28"
CHROME = "0.66 0.68 0.70 1"
TIRE = "0.035 0.035 0.038 1"
HEADLIGHT = "0.94 0.97 1 1"
AMBER = "1 0.34 0.015 1"
TAIL = "0.75 0.025 0.02 1"
PLATE = "0.94 0.94 0.92 1"
MATERIAL_RGBA = {
    "black_matte": BLACK,
    "glass": GLASS,
    "trim": CHROME,
    "wheel_metal": CHROME,
    "tire": TIRE,
    "headlight": HEADLIGHT,
    "amber": AMBER,
    "tail": TAIL,
    "plate": PLATE,
}
CURRENT_COLOR = "default"
VISUAL = 'contype="0" conaffinity="0" density="0" group="1"'
WHEEL_TURN = "1.57079632679 0 0"


def fmt(values) -> str:
    return " ".join(f"{value:g}" for value in values)


def box(name, pos, size, material, euler=None, indent="      ") -> str:
    turn = f' euler="{fmt(euler)}"' if euler else ""
    rgba = COLORS[CURRENT_COLOR] if material == "body_paint" else MATERIAL_RGBA.get(material)
    tint = f' rgba="{rgba}"' if rgba else ""
    return f'{indent}<geom name="{name}_visual" type="box" pos="{fmt(pos)}" size="{fmt(size)}"{turn} material="{material}"{tint} {VISUAL}/>'


def cylinder(name, pos, size, material, euler=None, indent="      ") -> str:
    turn = f' euler="{euler}"' if euler else ""
    rgba = COLORS[CURRENT_COLOR] if material == "body_paint" else MATERIAL_RGBA.get(material)
    tint = f' rgba="{rgba}"' if rgba else ""
    return f'{indent}<geom name="{name}_visual" type="cylinder" pos="{fmt(pos)}" size="{fmt(size)}"{turn} material="{material}"{tint} {VISUAL}/>'


def capsule(name, start, end, radius, material, indent="      ") -> str:
    rgba = COLORS[CURRENT_COLOR] if material == "body_paint" else MATERIAL_RGBA.get(material)
    tint = f' rgba="{rgba}"' if rgba else ""
    return f'{indent}<geom name="{name}_visual" type="capsule" fromto="{fmt((*start, *end))}" size="{radius:g}" material="{material}"{tint} {VISUAL}/>'


def rounded_box(name, pos, size, radius, material, indent="      ") -> list[str]:
    """Use the Car 1 primitive recipe: three cores plus twelve capsule edges."""
    (x, y, z), (a, b, c), r = pos, size, radius
    if not 0 < r <= min(size):
        raise ValueError(f"{name}: invalid radius {r}")
    geoms = [
        box(f"{name}_x", pos, (a, b - r, c - r), material, indent=indent),
        box(f"{name}_y", pos, (a - r, b, c - r), material, indent=indent),
        box(f"{name}_z", pos, (a - r, b - r, c), material, indent=indent),
    ]
    number = 0
    for axis in range(3):
        half = (a, b, c)
        others = [index for index in range(3) if index != axis]
        for s1 in (-1, 1):
            for s2 in (-1, 1):
                start, end = [x, y, z], [x, y, z]
                start[axis] -= half[axis] - r
                end[axis] += half[axis] - r
                for index, sign in zip(others, (s1, s2)):
                    offset = sign * (half[index] - r)
                    start[index] += offset
                    end[index] += offset
                geoms.append(capsule(f"{name}_edge{number}", start, end, r, material, indent))
                number += 1
    return geoms


def mirrored(maker, name, pos, *args):
    x, y, z = pos
    return [maker(f"{name}_left", (x, y, z), *args), maker(f"{name}_right", (x, -y, z), *args)]


def wheel(name, indent="          ") -> str:
    """A 16-inch alloy: tyre, dark well, five twin spokes, rim lip and hub (visual only).

    The wheel's local frame: axis along y after WHEEL_TURN; the outer face is at
    local +z of the turned cylinder, i.e. along +y for the left side. Spokes and
    the lip sit on both faces so the wheel reads the same from either side.
    """
    import math
    parts = [
        cylinder(f"{name}_tire", (0, 0, 0), (0.31, 0.105), "tire", WHEEL_TURN, indent),
        cylinder(f"{name}_well", (0, 0, 0), (0.205, 0.108), "black_matte", WHEEL_TURN, indent),
        cylinder(f"{name}_hub", (0, 0, 0), (0.055, 0.118), "wheel_metal", WHEEL_TURN, indent),
    ]
    for face, y in (("out", 0.112), ("in", -0.112)):
        for k in range(10):                                   # rim lip
            a = 2 * math.pi * k / 10
            parts.append(f'{indent}<geom name="{name}_lip_{face}_{k}_visual" type="box" pos="{0.198 * math.cos(a):.4f} {y:g} {0.198 * math.sin(a):.4f}" '
                         f'size="0.066 0.008 0.012" euler="0 {-a + math.pi / 2:.4f} 0" material="wheel_metal" {VISUAL}/>')
        for k in range(5):                                    # twin spokes
            for off in (-0.13, 0.13):
                a = 2 * math.pi * k / 5 + off
                parts.append(f'{indent}<geom name="{name}_spoke_{face}_{k}_{"a" if off < 0 else "b"}_visual" type="box" '
                             f'pos="{0.125 * math.cos(a):.4f} {y:g} {0.125 * math.sin(a):.4f}" size="0.072 0.009 0.013" '
                             f'euler="0 {-a:.4f} 0" material="wheel_metal" {VISUAL}/>')
    return "\n".join(parts)


def steered(side, y) -> str:
    return f'''      <body name="front_{side}_steer" pos="1.30 {y:g} 0">
        <inertial pos="0 0 0" mass="1" diaginertia="0.01 0.01 0.01"/>
        <joint name="front_{side}_steer_joint" type="hinge" axis="0 0 1" range="-0.80 0.80" damping="0.2" armature="0.02"/>
        <body name="front_{side}_wheel">
          <joint name="front_{side}_wheel_joint" type="hinge" axis="0 1 0" damping="0.1" armature="0.02"/>
{wheel(f"front_{side}")}
        </body>
      </body>'''


def driven(side, y) -> str:
    return f'''      <body name="rear_{side}_wheel" pos="-1.30 {y:g} 0">
        <joint name="rear_{side}_wheel_joint" type="hinge" axis="0 1 0" damping="0.1" armature="0.02"/>
{wheel(f"rear_{side}", "        ")}
      </body>'''


def mesh_geom(name, mesh, material) -> str:
    rgba = COLORS[CURRENT_COLOR] if material == "body_paint" else MATERIAL_RGBA.get(material)
    tint = f' rgba="{rgba}"' if rgba else ""
    return f'      <geom name="{name}_visual" type="mesh" mesh="{mesh}" material="{material}"{tint} {VISUAL}/>'


def on_slope(name, x0, z0, x1, z1, y, half_y, half_t, material, out=0.006):
    """A thin panel lying on the profile segment (x0,z0)-(x1,z1), centred at y."""
    import math
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    length = math.hypot(x1 - x0, z1 - z0) / 2
    pitch = math.atan2(z1 - z0, x1 - x0)          # rotation about y
    nx, nz = math.sin(pitch), -math.cos(pitch)     # outward normal of a front/top face
    if nz < 0:
        nx, nz = -nx, -nz
    return box(name, (cx + nx * out, y, cz + nz * out), (length, half_y, half_t), material, (0, -pitch, 0))


def body_geoms() -> list[str]:
    """The lofted body (config/body_mesh.py, one mesh per material) and its details."""
    from body_mesh import plan_half_width, side_half_width, z_belt

    def side_y(x, z, gap=0.004):
        return side_half_width(x, z) + gap

    geoms = [
        mesh_geom("body_paint", "car2_body_paint", "body_paint"),
        mesh_geom("body_black", "car2_body_black_matte", "black_matte"),
        mesh_geom("body_glass", "car2_body_glass", "glass"),
        # Front: slim headlights at the hood's leading edge, an upper grille between them,
        # a wide lower intake, the plate in between, fog lamp bezels at the corners.
        *[on_slope(f"headlight_{s}", 2.172, 0.330, 2.110, 0.430, k * 0.41, 0.165, 0.008, "headlight") for s, k in (("left", 1), ("right", -1))],
        *[box(f"indicator_{s}", (2.118, k * 0.60, 0.40), (0.012, 0.03, 0.016), "amber") for s, k in (("left", 1), ("right", -1))],
        box("grille_upper", (2.180, 0, 0.30), (0.012, 0.24, 0.035), "black_matte", (0, -0.2, 0)),
        box("grille_bar", (2.190, 0, 0.30), (0.004, 0.22, 0.005), "trim", (0, -0.2, 0)),
        box("grille_lower", (2.193, 0, 0.06), (0.010, 0.38, 0.06), "black_matte"),
        box("front_plate", (2.200, 0, 0.19), (0.006, 0.165, 0.048), "plate"),
        *[box(f"fog_{s}", (2.192, k * 0.50, 0.07), (0.010, 0.07, 0.03), "black_matte") for s, k in (("left", 1), ("right", -1))],
        # Rear: tail lights at the hatch glass's lower corners, the plate, the stop lamp, the wiper.
        *[on_slope(f"tail_light_{s}", -2.04, 0.725, -2.11, 0.625, k * 0.58, 0.16, 0.008, "tail") for s, k in (("left", 1), ("right", -1))],
        *[box(f"tail_side_{s}", (-1.98, k * (side_y(-1.98, 0.70) - 0.004), 0.69), (0.07, 0.005, 0.04), "tail") for s, k in (("left", 1), ("right", -1))],
        box("rear_plate_recess", (-2.193, 0, 0.36), (0.006, 0.20, 0.075), "black_matte"),
        box("rear_plate", (-2.197, 0, 0.36), (0.006, 0.17, 0.055), "plate"),
        box("rear_lower", (-2.192, 0, 0.04), (0.010, 0.62, 0.06), "black_matte"),
        box("high_stop_lamp", (-1.79, 0, 1.12), (0.012, 0.18, 0.010), "tail"),
        box("rear_wiper", (-1.95, 0.08, 0.90), (0.008, 0.22, 0.006), "black_matte", (0.45, 0, 0)),
        # Sides: door mirrors at the window's front corner on the door, door handles.
        *[box(f"mirror_{s}", (0.74, k * (side_y(0.74, 0.63) + 0.075), 0.695), (0.07, 0.062, 0.045), "body_paint") for s, k in (("left", 1), ("right", -1))],
        *[box(f"mirror_glass_{s}", (0.668, k * (side_y(0.74, 0.63) + 0.075), 0.695), (0.004, 0.055, 0.037), "black_matte") for s, k in (("left", 1), ("right", -1))],
        *[box(f"mirror_arm_{s}", (0.76, k * (side_y(0.76, 0.63) + 0.015), 0.66), (0.035, 0.02, 0.015), "black_matte") for s, k in (("left", 1), ("right", -1))],
        *[box(f"handle_{door}_{s}", (x, k * side_y(x, 0.55, 0.012), 0.55), (0.075, 0.010, 0.014), "trim")
          for door, x in (("front", 0.02), ("rear", -1.02)) for s, k in (("left", 1), ("right", -1))],
        # Cabin: a dashboard under the windshield (hides the inside of the body from the seats).
        box("dashboard", (0.56, 0, 0.565), (0.30, 0.82, 0.02), "black_matte", (0, -0.06, 0)),
        box("firewall", (0.78, 0, 0.495), (0.06, 0.82, 0.205), "black_matte"),
        box("dashboard_lower", (0.45, 0, 0.37), (0.20, 0.80, 0.17), "black_matte"),
        box("steering_column", (0.26, -0.38, 0.58), (0.08, 0.03, 0.03), "black_matte", (0, 0.45, 0)),
        # The driver-assist camera behind the windshield top.
        box("adas_camera", (0.14, 0, 1.085), (0.04, 0.06, 0.03), "black_matte"),
    ]
    return geoms


def model(color_name: str) -> str:
    global CURRENT_COLOR
    CURRENT_COLOR = color_name
    color = COLORS[color_name]
    return f'''<mujoco model="hakoniwa_car2_{color_name}">
  <compiler angle="radian" autolimits="true"/>
  <asset>
    <material name="body_paint" rgba="{color}" specular="0.45" shininess="0.55" reflectance="0.12"/>
    <material name="black_matte" rgba="{BLACK}" specular="0.04" shininess="0.08"/>
    <material name="glass" rgba="{GLASS}" specular="0.55" shininess="0.65" reflectance="0.12"/>
    <material name="trim" rgba="{CHROME}" specular="0.35" shininess="0.45"/>
    <material name="wheel_metal" rgba="{CHROME}" specular="0.55" shininess="0.6"/>
    <material name="tire" rgba="{TIRE}" specular="0.02" shininess="0.04"/>
    <material name="headlight" rgba="{HEADLIGHT}" specular="0.7" shininess="0.8"/>
    <material name="amber" rgba="{AMBER}" specular="0.45" shininess="0.55"/>
    <material name="tail" rgba="{TAIL}" specular="0.45" shininess="0.55"/>
    <material name="plate" rgba="{PLATE}" specular="0.15" shininess="0.2"/>
    <mesh name="car2_body_paint" file="../config/meshes/body_body_paint.obj" inertia="shell"/>
    <mesh name="car2_body_black_matte" file="../config/meshes/body_black_matte.obj" inertia="shell"/>
    <mesh name="car2_body_glass" file="../config/meshes/body_glass.obj" inertia="shell"/>
  </asset>
  <worldbody>
    <body name="vehicle">
{chr(10).join(body_geoms())}
{steered("left", 0.76)}
{steered("right", -0.76)}
{driven("left", 0.76)}
{driven("right", -0.76)}
    </body>
  </worldbody>
</mujoco>
'''


def main() -> None:
    directory = Path(__file__).parent
    import sys
    sys.path.insert(0, str(directory))
    from body_mesh import build
    build(directory / "meshes")
    for color_name in COLORS:
        filename = "model.xml" if color_name == "default" else f"model-{color_name}.xml"
        target = directory / filename
        target.write_text(model(color_name), encoding="utf-8")
        print(f"Wrote {target}")


if __name__ == "__main__":
    main()
