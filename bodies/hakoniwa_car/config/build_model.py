#!/usr/bin/env python3
"""Write model.xml: the Hakoniwa Car's visual model and joint structure.

Every visual geom is a MuJoCo primitive. The body panels (the cab, the cargo
box, the roof pod, the nose) are rounded boxes: three boxes, each shrunk by
the radius in two axes, and twelve capsules along the edges (their round
ends make the corners). Details (windows, lights, door lines) sit on the flat
parts of the panels. Change the numbers here and run it again, then the Forge:

  python bodies/hakoniwa_car/config/build_model.py
  python tools/ackermann/forge.py hakoniwa_car
"""

from __future__ import annotations

from pathlib import Path

WHITE = "0.93 0.94 0.94 1"
WHITE_DOOR = "0.88 0.89 0.90 1"
GREY = "0.23 0.25 0.28 1"
BLACK = "0.07 0.08 0.10 1"
BLUE = "0.25 0.65 1.00 1"
RED = "0.85 0.12 0.10 1"
EYE = "0.97 0.98 1.00 1"
TIRE = "0.08 0.08 0.08 1"
HUB = "0.45 0.47 0.50 1"
VISUAL = 'contype="0" conaffinity="0" density="0" group="1"'


def fmt(values) -> str:
    return " ".join(f"{value:g}" for value in values)


def box(name, pos, size, rgba, indent="      "):
    return f'{indent}<geom name="{name}_visual" type="box" pos="{fmt(pos)}" size="{fmt(size)}" rgba="{rgba}" {VISUAL}/>'


def cylinder(name, pos, size, rgba, euler=None, indent="      "):
    turn = f' euler="{euler}"' if euler else ""
    return (f'{indent}<geom name="{name}_visual" type="cylinder" pos="{fmt(pos)}" size="{fmt(size)}"{turn} '
            f'rgba="{rgba}" {VISUAL}/>')


def rounded_box(name, pos, size, radius, rgba, indent="      "):
    """A box with its edges and corners rounded by `radius` (at most its smallest half size)."""
    (x, y, z), (a, b, c), r = pos, size, radius
    if not 0 < r <= min(size):
        raise ValueError(f"{name}: radius {r} must be within (0, {min(size)}]")
    geoms = [
        box(f"{name}_x", pos, (a, b - r, c - r), rgba, indent),
        box(f"{name}_y", pos, (a - r, b, c - r), rgba, indent),
        box(f"{name}_z", pos, (a - r, b - r, c), rgba, indent),
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
                geoms.append(f'{indent}<geom name="{name}_edge{number}_visual" type="capsule" '
                             f'fromto="{fmt(start + end)}" size="{r:g}" rgba="{rgba}" {VISUAL}/>')
                number += 1
    return geoms


def fender(name, centre, radius, thickness, rgba, segments=7, indent="      "):
    """A curved fender over a wheel: capsules along a half circle above the
    wheel centre (x, y, z), from the front to the back at the wheel's height."""
    import math

    x, y, z = centre
    points = [(x + radius * math.cos(math.pi * step / segments), y, z + radius * math.sin(math.pi * step / segments))
              for step in range(segments + 1)]
    return [f'{indent}<geom name="{name}_{index}_visual" type="capsule" fromto="{fmt(start + end)}" '
            f'size="{thickness:g}" rgba="{rgba}" {VISUAL}/>' for index, (start, end) in enumerate(zip(points, points[1:]))]


def mirrored(maker, name, pos, *rest):
    """A left (+y) and a right (-y) copy."""
    x, y, z = pos
    return [maker(f"{name}_left", (x, y, z), *rest), maker(f"{name}_right", (x, -y, z), *rest)]


BODY = [
    "      <!-- Lower chassis (dark grey), between and outside the wheels -->",
    box("chassis_core", (0, 0, -0.12), (1.06, 0.38, 0.13), GREY),
    box("front_bumper", (1.04, 0, -0.13), (0.06, 0.55, 0.12), GREY),
    box("rear_bumper", (-1.04, 0, -0.13), (0.06, 0.55, 0.12), GREY),
    *mirrored(box, "side_skirt", (0, 0.53, -0.10), (0.47, 0.05, 0.10), GREY),
    "      <!-- A dark band along the lower sides, the white arches over the wheels on it -->",
    *mirrored(box, "side_band", (0, 0.594, 0.05), (1.08, 0.008, 0.08), GREY),
    *(geom for wheel_x in (0.75, -0.75) for side, wheel_y in (("left", 0.60), ("right", -0.60))
      for geom in fender(f"fender_{'front' if wheel_x > 0 else 'rear'}_{side}", (wheel_x, wheel_y, -0.17), 0.31, 0.04, WHITE)),
    "      <!-- Cab (front), rounded -->",
    *rounded_box("cab", (0.70, 0, 0.47), (0.36, 0.56, 0.46), 0.14, WHITE),
    *rounded_box("cab_nose", (1.07, 0, 0.12), (0.04, 0.52, 0.11), 0.03, WHITE),
    box("windshield", (1.065, 0, 0.52), (0.012, 0.40, 0.27), BLACK),
    *mirrored(box, "side_window", (0.80, 0.565, 0.58), (0.11, 0.006, 0.20), BLACK),
    *mirrored(box, "eye", (1.08, 0.17, 0.52), (0.006, 0.055, 0.065), EYE),
    box("front_camera", (1.08, 0, 0.76), (0.006, 0.08, 0.03), BLACK),
    box("led_strip", (1.115, 0, 0.17), (0.006, 0.36, 0.018), BLUE),
    *mirrored(box, "headlight", (1.115, 0.46, 0.17), (0.006, 0.05, 0.025), BLUE),
    *mirrored(box, "side_camera", (0.97, 0.60, 0.78), (0.05, 0.04, 0.05), BLACK),
    *mirrored(box, "side_marker", (0.55, 0.565, 0.40), (0.04, 0.006, 0.025), BLACK),
    "      <!-- Roof sensor pod (rounded) and LiDAR -->",
    *rounded_box("roof_pod", (0.72, 0, 0.99), (0.24, 0.36, 0.06), 0.05, WHITE),
    *mirrored(box, "roof_sensor", (0.90, 0.28, 1.07), (0.03, 0.03, 0.03), BLACK),
    cylinder("lidar_base", (0.72, 0, 1.12), (0.13, 0.07), BLACK),
    cylinder("lidar_ring", (0.72, 0, 1.21), (0.132, 0.02), BLUE),
    cylinder("lidar_top", (0.72, 0, 1.29), (0.12, 0.06), BLACK),
    "      <!-- Between cab and cargo box -->",
    box("pillar", (0.30, 0, 0.43), (0.04, 0.54, 0.42), GREY),
    "      <!-- Cargo box (rear), rounded -->",
    *rounded_box("cargo", (-0.40, 0, 0.53), (0.68, 0.58, 0.52), 0.08, WHITE),
    *mirrored(box, "cargo_seam", (-0.40, 0.582, 0.55), (0.006, 0.003, 0.42), GREY),
    *mirrored(box, "cargo_handle", (-0.85, 0.585, 0.32), (0.07, 0.005, 0.03), GREY),
    box("rear_door_frame", (-1.082, 0, 0.55), (0.003, 0.44, 0.42), GREY),
    box("rear_door", (-1.086, 0, 0.55), (0.003, 0.42, 0.40), WHITE_DOOR),
    box("rear_handle", (-1.092, 0, 0.30), (0.004, 0.08, 0.03), GREY),
    *mirrored(box, "tail_light", (-1.09, 0.475, 0.55), (0.004, 0.02, 0.14), RED),
    *mirrored(box, "rear_reflector", (-1.10, 0.38, -0.10), (0.004, 0.03, 0.05), RED),
]

WHEEL_TURN = "1.57079632679 0 0"


def wheel(name, indent):
    return "\n".join([
        cylinder(f"{name}_tire", (0, 0, 0), (0.25, 0.10), TIRE, WHEEL_TURN, indent),
        cylinder(f"{name}_hub", (0, 0, 0), (0.13, 0.102), HUB, WHEEL_TURN, indent),
        cylinder(f"{name}_cap", (0, 0, 0), (0.05, 0.104), BLACK, WHEEL_TURN, indent),
    ])


def steered(side, y):
    return f'''      <body name="front_{side}_steer" pos="0.75 {y:g} -0.17">
        <inertial pos="0 0 0" mass="0.3" diaginertia="0.001 0.001 0.001"/>
        <joint name="front_{side}_steer_joint" type="hinge" axis="0 0 1"
               range="-0.80 0.80" damping="0.05" armature="0.01"/>
        <body name="front_{side}_wheel">
          <joint name="front_{side}_wheel_joint" type="hinge" axis="0 1 0"
                 damping="0.05" armature="0.01"/>
{wheel(f"front_{side}", "          ")}
        </body>
      </body>'''


def driven(side, y):
    return f'''      <body name="rear_{side}_wheel" pos="-0.75 {y:g} -0.17">
        <joint name="rear_{side}_wheel_joint" type="hinge" axis="0 1 0"
               damping="0.05" armature="0.01"/>
{wheel(f"rear_{side}", "        ")}
      </body>'''


def model() -> str:
    return f'''<mujoco model="hakoniwa_car">
  <compiler angle="radian" autolimits="true"/>

  <!--
    Hakoniwa Car: a small autonomous delivery vehicle authored for Hakoniwa
    from boxes, cylinders and capsules (cab in front, cargo box behind, roof
    LiDAR; the panels rounded). Written by build_model.py: change it there.
    Every geom here is visual only (group 1, no contact, no mass). Physical
    collision geoms and mass, actuators, contact excludes, and the world are
    injected from the sibling YAML files by tools/ackermann/forge.py.
    The vehicle frame is 0.42 m above the ground (the wheel centres 0.25 m).
  -->
  <worldbody>
    <body name="vehicle">
{chr(10).join(BODY)}

{steered("left", 0.50)}

{steered("right", -0.50)}

{driven("left", 0.50)}

{driven("right", -0.50)}
    </body>
  </worldbody>
</mujoco>
'''


if __name__ == "__main__":
    target = Path(__file__).with_name("model.xml")
    target.write_text(model(), encoding="utf-8")
    print(f"Wrote {target}")
