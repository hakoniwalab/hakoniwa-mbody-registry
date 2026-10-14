#!/usr/bin/env python3
"""Build colour variants of the generic Hakoniwa medium box truck."""

from pathlib import Path
import math

CAB_COLORS = {
    "default": "0.035 0.25 0.58 1",
    "white": "0.88 0.89 0.90 1",
    "green": "0.05 0.38 0.18 1",
}
SILVER = "0.72 0.74 0.75 1"
DARK = "0.035 0.04 0.045 1"
GLASS = "0.08 0.15 0.18 1"
CHROME = "0.65 0.67 0.68 1"
TIRE = "0.025 0.025 0.028 1"
WHITE = "0.95 0.96 1 1"
RED = "0.8 0.02 0.01 1"
AMBER = "1 0.35 0.01 1"
YELLOW = "0.95 0.72 0.02 1"
VISUAL = 'contype="0" conaffinity="0" density="0" group="1"'
WHEEL_TURN = "1.57079632679 0 0"

# Empty-cargo-box suspension baseline.  The model's 5,950 kg vehicle body is
# sprung; the four 12 kg tires and two 1 kg steering carriers are unsprung.
# The longitudinal CG is rearward, so front and rear corner rates are derived
# separately from static axle load instead of splitting the mass equally.
SUSPENSION_NATURAL_FREQUENCY_HZ = 1.70
SUSPENSION_DAMPING_RATIO = 0.35
SUSPENSION_TRAVEL_M = 0.10
GRAVITY_M_S2 = 9.81
SPRUNG_MASS_KG = 5950.0
FRONT_AXLE_X_M = 2.15
REAR_AXLE_X_M = -2.15
SPRUNG_CG_X_M = -0.60


def corner_sprung_masses() -> tuple[float, float]:
    """Return front and rear sprung mass per wheel from static axle loads."""
    wheelbase = FRONT_AXLE_X_M - REAR_AXLE_X_M
    front_axle_mass = SPRUNG_MASS_KG * (
        (SPRUNG_CG_X_M - REAR_AXLE_X_M) / wheelbase
    )
    rear_axle_mass = SPRUNG_MASS_KG - front_axle_mass
    return front_axle_mass / 2.0, rear_axle_mass / 2.0


def suspension_parameters(axle: str) -> tuple[float, float, float]:
    """Return stiffness, damping and preload reference for one corner."""
    front_mass, rear_mass = corner_sprung_masses()
    if axle == "front":
        corner_mass = front_mass
    elif axle == "rear":
        corner_mass = rear_mass
    else:
        raise ValueError(f"unknown axle: {axle}")
    omega = 2 * math.pi * SUSPENSION_NATURAL_FREQUENCY_HZ
    stiffness = corner_mass * omega**2
    damping = 2 * SUSPENSION_DAMPING_RATIO * math.sqrt(stiffness * corner_mass)
    springref = -GRAVITY_M_S2 / omega**2
    return stiffness, damping, springref


def suspension_joint(name: str, axle: str, indent: str = "        ") -> str:
    stiffness, damping, springref = suspension_parameters(axle)
    return (
        f'{indent}<joint name="{name}_suspension" type="slide" axis="0 0 1" '
        f'range="{-SUSPENSION_TRAVEL_M:g} {SUSPENSION_TRAVEL_M:g}" limited="true" '
        f'stiffness="{stiffness:.9g}" damping="{damping:.9g}" '
        f'springref="{springref:.9g}"/>'
    )


def fmt(values):
    return " ".join(f"{value:g}" for value in values)


def box(name, pos, size, material, indent="      "):
    return f'{indent}<geom name="{name}_visual" type="box" pos="{fmt(pos)}" size="{fmt(size)}" material="{material}" {VISUAL}/>'


def cylinder(name, pos, size, material, euler=None, indent="      "):
    turn = f' euler="{euler}"' if euler else ""
    return f'{indent}<geom name="{name}_visual" type="cylinder" pos="{fmt(pos)}" size="{fmt(size)}"{turn} material="{material}" {VISUAL}/>'


def capsule(name, start, end, radius, material, indent="      "):
    return f'{indent}<geom name="{name}_visual" type="capsule" fromto="{fmt((*start, *end))}" size="{radius:g}" material="{material}" {VISUAL}/>'


def rounded_box(name, pos, size, radius, material, indent="      "):
    """Car 1's rounded primitive recipe: three cores and twelve edge capsules."""
    (x, y, z), (a, b, c), r = pos, size, radius
    geoms = [
        box(f"{name}_x", pos, (a, b - r, c - r), material, indent),
        box(f"{name}_y", pos, (a - r, b, c - r), material, indent),
        box(f"{name}_z", pos, (a - r, b - r, c), material, indent),
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


def wheel(name, width, indent="          "):
    return "\n".join([
        cylinder(f"{name}_tire", (0, 0, 0), (0.45, width), "tire", WHEEL_TURN, indent),
        cylinder(f"{name}_rim", (0, 0, 0), (0.25, width + 0.004), "wheel_metal", WHEEL_TURN, indent),
        cylinder(f"{name}_hub", (0, 0, 0), (0.075, width + 0.008), "black_matte", WHEEL_TURN, indent),
    ])


def steered(side, y):
    return f'''      <body name="front_{side}_steer" pos="2.15 {y:g} 0">
        <inertial pos="0 0 0" mass="1" diaginertia="0.02 0.02 0.02"/>
{suspension_joint(f"front_{side}", "front")}
        <joint name="front_{side}_steer_joint" type="hinge" axis="0 0 1" range="-0.65 0.65" damping="0.5" armature="0.05"/>
        <body name="front_{side}_wheel">
          <joint name="front_{side}_wheel_joint" type="hinge" axis="0 1 0" damping="0.25" armature="0.08"/>
{wheel(f"front_{side}", 0.14)}
        </body>
      </body>'''


def driven(side, y):
    return f'''      <body name="rear_{side}_wheel" pos="-2.15 {y:g} 0">
{suspension_joint(f"rear_{side}", "rear")}
        <joint name="rear_{side}_wheel_joint" type="hinge" axis="0 1 0" damping="0.25" armature="0.08"/>
{wheel(f"rear_{side}", 0.18, "        ")}
      </body>'''


def body_geoms():
    geoms = [
        # Cab-over silhouette and opaque aluminium cargo box.
        box("frame", (0, 0, 0.34), (3.85, 0.72, 0.12), "black_matte"),
        *rounded_box("cab_lower", (2.82, 0, 0.67), (1.10, 1.10, 0.58), 0.08, "cab_paint"),
        *rounded_box("cab_upper", (2.72, 0, 1.63), (0.94, 1.08, 0.48), 0.08, "cab_paint"),
        box("windshield", (3.68, 0, 1.65), (0.018, 0.82, 0.33), "glass"),
        box("camera", (3.71, 0, 1.88), (0.025, 0.07, 0.035), "black_matte"),
        box("cargo_box", (-0.82, 0, 1.55), (2.96, 1.12, 1.20), "cargo_silver"),
        box("cargo_upper_panel", (-0.82, 1.125, 2.15), (2.86, 0.012, 0.52), "cargo_light"),
        box("cargo_lower_panel", (-0.82, 1.126, 0.94), (2.86, 0.012, 0.52), "cargo_dark"),
        box("cargo_roof", (-0.82, 0, 2.725), (3.00, 1.15, 0.025), "wheel_metal"),
        box("rear_door_left", (-3.80, 0.56, 1.55), (0.025, 0.54, 1.16), "cargo_light"),
        box("rear_door_right", (-3.80, -0.56, 1.55), (0.025, 0.54, 1.16), "cargo_light"),
        capsule("rear_door_seam", (-3.835, 0, 0.43), (-3.835, 0, 2.67), 0.018, "black_matte"),
        capsule("rear_lock_left", (-3.84, 0.18, 0.55), (-3.84, 0.18, 2.55), 0.025, "black_matte"),
        capsule("rear_lock_right", (-3.84, -0.18, 0.55), (-3.84, -0.18, 2.55), 0.025, "black_matte"),
        box("front_grille", (3.935, 0, 0.73), (0.02, 0.67, 0.19), "black_matte"),
        box("front_lower_bumper", (3.94, 0, 0.30), (0.045, 0.88, 0.11), "black_matte"),
        box("front_plate", (3.99, 0, 0.42), (0.025, 0.20, 0.075), "lamp_white"),
        box("rear_plate", (-3.96, 0, 0.35), (0.025, 0.20, 0.075), "lamp_white"),
        box("rear_bumper", (-3.92, 0, 0.22), (0.09, 1.02, 0.10), "black_matte"),
        box("underrun_bar", (-3.99, 0, 0.38), (0.055, 0.92, 0.10), "warning_yellow"),
        box("side_guard_left", (-0.20, 1.02, 0.38), (1.35, 0.045, 0.08), "wheel_metal"),
        box("side_guard_right", (-0.20, -1.02, 0.38), (1.35, 0.045, 0.08), "wheel_metal"),
    ]
    for side, y in (("left", 1.22), ("right", -1.22)):
        geoms += [
            box(f"mirror_arm_{side}", (3.30, y * 0.92, 1.72), (0.16, 0.025, 0.025), "black_matte"),
            box(f"mirror_{side}", (3.30, y, 1.72), (0.15, 0.08, 0.20), "black_matte"),
            box(f"side_window_{side}", (2.92, 1.086 if y > 0 else -1.086, 1.65), (0.50, 0.015, 0.32), "glass"),
            box(f"headlight_{side}", (3.96, 0.76 if y > 0 else -0.76, 0.77), (0.025, 0.20, 0.16), "lamp_white"),
            box(f"tail_red_{side}", (-3.96, 0.70 if y > 0 else -0.70, 0.58), (0.025, 0.16, 0.10), "tail_red"),
            box(f"tail_amber_{side}", (-3.96, 0.91 if y > 0 else -0.91, 0.58), (0.025, 0.07, 0.10), "warning_amber"),
            box(f"reflector_red_{side}", (-4.05, 0.58 if y > 0 else -0.58, 0.38), (0.018, 0.20, 0.055), "tail_red"),
        ]
    return geoms


def model(color_name):
    cab = CAB_COLORS[color_name]
    return f'''<mujoco model="hakoniwa_truck_{color_name}">
  <compiler angle="radian" autolimits="true"/>
  <asset>
    <material name="cab_paint" rgba="{cab}" specular="0.28" shininess="0.35" reflectance="0.06"/>
    <material name="black_matte" rgba="{DARK}" specular="0.035" shininess="0.06"/>
    <material name="glass" rgba="{GLASS}" specular="0.5" shininess="0.6" reflectance="0.1"/>
    <material name="cargo_silver" rgba="{SILVER}" specular="0.26" shininess="0.32"/>
    <material name="cargo_light" rgba="0.78 0.79 0.80 1" specular="0.24" shininess="0.30"/>
    <material name="cargo_dark" rgba="0.66 0.68 0.69 1" specular="0.22" shininess="0.28"/>
    <material name="wheel_metal" rgba="{CHROME}" specular="0.5" shininess="0.58"/>
    <material name="tire" rgba="{TIRE}" specular="0.02" shininess="0.04"/>
    <material name="lamp_white" rgba="{WHITE}" specular="0.65" shininess="0.75"/>
    <material name="tail_red" rgba="{RED}" specular="0.4" shininess="0.5"/>
    <material name="warning_amber" rgba="{AMBER}" specular="0.4" shininess="0.5"/>
    <material name="warning_yellow" rgba="{YELLOW}" specular="0.15" shininess="0.2"/>
  </asset>
  <worldbody>
    <body name="vehicle">
      <inertial pos="-0.6 0 0.75" mass="5950" diaginertia="4700 34000 34700"/>
{chr(10).join(body_geoms())}
{steered("left", 0.925)}
{steered("right", -0.925)}
{driven("left", 0.85)}
{driven("right", -0.85)}
    </body>
  </worldbody>
</mujoco>
'''


def main():
    directory = Path(__file__).parent
    for color_name in CAB_COLORS:
        filename = "model.xml" if color_name == "default" else f"model-{color_name}.xml"
        target = directory / filename
        target.write_text(model(color_name), encoding="utf-8")
        print(f"Wrote {target}")


if __name__ == "__main__":
    main()
