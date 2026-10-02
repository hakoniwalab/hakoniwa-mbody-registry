#!/usr/bin/env python3
"""Write model.xml: the Hakoniwa Cart's visual model and joint structure.

The Hakoniwa Cart is a four-seat cart (two rows facing forward) under a long
white roof: a rounded white nose with two round head lamps and a white LED
bar between them, a dark bumper below, seats on white pedestals and a grab
bar behind the rear row, round red tail lamps at the back.

Every visual geom is a MuJoCo primitive. The panels are rounded boxes: three
boxes, each shrunk by the radius in two axes, and twelve capsules along the
edges (their round ends make the corners). The roof is held by black pillars
(capsules); the windshield is an open frame. Change the numbers here and run
it again, then the Forge:

  python bodies/hakoniwa_cart/config/build_model.py
  python tools/ackermann/forge.py hakoniwa_cart
"""

from __future__ import annotations

import math
from pathlib import Path

WHITE = "0.95 0.95 0.94 1"
ORANGE = "1.00 0.50 0.12 1"
SEAT = "0.84 0.84 0.82 1"
SEAT_DARK = "0.16 0.17 0.19 1"
GREY = "0.22 0.23 0.25 1"
BLACK = "0.07 0.08 0.10 1"
UNDER_ROOF = "0.80 0.80 0.78 1"
LAMP = "1 0.97 0.86 1"
AMBER = "1.00 0.62 0.05 1"
RED = "0.85 0.12 0.10 1"
LENS = "0.72 0.75 0.78 1"
TIRE = "0.08 0.08 0.08 1"
RIM = "0.30 0.31 0.33 1"
SILVER = "0.70 0.72 0.74 1"
VISUAL = 'contype="0" conaffinity="0" density="0" group="1"'

ALONG_X = "0 1.57079632679 0"   # a cylinder's axis (z) turned onto x
ALONG_Y = "1.57079632679 0 0"   # ... onto y (the wheels)

# The layout (the vehicle frame: x forward, y left, z up; its origin midway
# between the axles, 0.45 m above the ground).
WHEEL_X = 1.05        # wheelbase 2.10 m
WHEEL_Y = 0.52        # track 1.04 m
WHEEL_Z = -0.18       # the wheel centres 0.27 m above the ground
WHEEL_R = 0.27
FRONT_ROW_X = 0.20    # the seat cushions' centres
REAR_ROW_X = -1.00
SEAT_Y = 0.26         # the driver sits on the left (+y)


def fmt(values) -> str:
    return " ".join(f"{value:g}" for value in values)


def box(name, pos, size, rgba, indent="      ", euler=None):
    turn = f' euler="{euler}"' if euler else ""
    return f'{indent}<geom name="{name}_visual" type="box" pos="{fmt(pos)}" size="{fmt(size)}"{turn} rgba="{rgba}" {VISUAL}/>'


def cylinder(name, pos, size, rgba, euler=None, indent="      "):
    turn = f' euler="{euler}"' if euler else ""
    return (f'{indent}<geom name="{name}_visual" type="cylinder" pos="{fmt(pos)}" size="{fmt(size)}"{turn} '
            f'rgba="{rgba}" {VISUAL}/>')


def capsule(name, start, end, radius, rgba, indent="      "):
    return (f'{indent}<geom name="{name}_visual" type="capsule" fromto="{fmt(list(start) + list(end))}" '
            f'size="{radius:g}" rgba="{rgba}" {VISUAL}/>')


def rounded_box(name, pos, size, radius, rgba, indent="      ", pitch=0.0):
    """A box with its edges and corners rounded by `radius` (less than its
    smallest half size), turned by `pitch` about y (MuJoCo's sense: positive
    turns x down) round its centre."""
    (x, y, z), (a, b, c), r = pos, size, radius
    if not 0 < r <= min(size) - 0.005 + 1e-9:  # the edge capsules must keep some length
        raise ValueError(f"{name}: radius {r} must be within (0, {min(size)})")
    cp, sp = math.cos(pitch), math.sin(pitch)

    def turned(dx, dy, dz):  # an offset from the centre, turned about y
        return (x + cp * dx + sp * dz, y + dy, z - sp * dx + cp * dz)

    euler = f"0 {pitch:g} 0" if pitch else None
    geoms = [
        box(f"{name}_x", pos, (a, b - r, c - r), rgba, indent, euler),
        box(f"{name}_y", pos, (a - r, b, c - r), rgba, indent, euler),
        box(f"{name}_z", pos, (a - r, b - r, c), rgba, indent, euler),
    ]
    number = 0
    half = (a, b, c)
    for axis in range(3):
        others = [index for index in range(3) if index != axis]
        for s1 in (-1, 1):
            for s2 in (-1, 1):
                start, end = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
                start[axis] -= half[axis] - r
                end[axis] += half[axis] - r
                for index, sign in zip(others, (s1, s2)):
                    start[index] += sign * (half[index] - r)
                    end[index] += sign * (half[index] - r)
                geoms.append(capsule(f"{name}_edge{number}", turned(*start), turned(*end), r, rgba, indent))
                number += 1
    return geoms

def span(name, x0, x1, y_half, z0, z1, radius, rgba):
    """A rounded box given by its extent (front/back x, half width, bottom/top z)."""
    return rounded_box(name, ((x0 + x1) / 2, 0, (z0 + z1) / 2), ((x1 - x0) / 2, y_half, (z1 - z0) / 2), radius, rgba)


def slanted(name, front, back, y, half_y, half_thickness, side, rgba):
    """A plate in the x-z plane whose edge runs from `front` (x, z) to `back`
    (x, z), lying `side` of it (+1 above, -1 below): a slanted line."""
    (x0, z0), (x1, z1) = front, back
    dx, dz = x0 - x1, z0 - z1
    angle = math.atan2(-dz, dx)  # turning x about y onto the edge
    normal = (math.sin(angle), math.cos(angle))
    half_length = math.hypot(dx, dz) / 2
    centre = ((x0 + x1) / 2 + side * half_thickness * normal[0], y, (z0 + z1) / 2 + side * half_thickness * normal[1])
    return (f'      <geom name="{name}_visual" type="box" pos="{fmt(centre)}" '
            f'size="{fmt((half_length, half_y, half_thickness))}" euler="0 {angle:g} 0" rgba="{rgba}" {VISUAL}/>')


def ellipsoid(name, pos, radii, rgba, indent="      "):
    return f'{indent}<geom name="{name}_visual" type="ellipsoid" pos="{fmt(pos)}" size="{fmt(radii)}" rgba="{rgba}" {VISUAL}/>'


FACE_X = 1.46   # the front of the white face


def nose():
    """The front, seen from the side a trapezoid: as short as the cowl at the
    top, widening down to the front wheel. Forward, the face leans back above
    the lamps (the forehead) and stands upright below them; backward, the
    side's rear edge runs from the windshield's foot down and back behind the
    wheel. The white side wraps the wheel arch from above, a dark grey fender
    along the arch. On top, a black cowl; below, the bumper (with the lamps)."""
    wheel = (WHEEL_X, WHEEL_Z)
    rear_line = [(1.02, 0.58), (0.83, 0.29), (0.64, 0.0)]  # the side's rear edge, top to bottom
    geoms = [
        *span("face", 1.30, FACE_X, 0.60, 0.0, 0.40, 0.074, WHITE),
        # The forehead: leaning back 28.6 degrees from the lamps' top up to the cowl
        *rounded_box("forehead", (1.330, 0, 0.432), (0.08, 0.60, 0.14), 0.074, WHITE, pitch=-0.4995),
        *span("cowl", 1.00, 1.32, 0.56, 0.50, 0.60, 0.04, SEAT_DARK),
    ]
    for name, sign in (("left", 1), ("right", -1)):
        plate = sign * 0.585
        geoms += [
            box(f"side_{name}", (1.18, plate, 0.37), (0.16, 0.015, 0.21), WHITE),
            slanted(f"side_rear_{name}", rear_line[0], rear_line[1], plate, 0.015, 0.085, -1, WHITE),
            slanted(f"side_rear_foot_{name}", rear_line[1], rear_line[2], plate, 0.015, 0.05, -1, WHITE),
            *arch_band(f"side_arch_{name}", wheel, plate, 0.36, 0.45, 0.015, WHITE),
            # Dark inside the nose, seen from the footwell
            slanted(f"firewall_{name}", rear_line[0], rear_line[1], sign * 0.30, 0.27, 0.01, -1, SEAT_DARK),
            slanted(f"firewall_foot_{name}", rear_line[1], rear_line[2], sign * 0.30, 0.27, 0.01, -1, SEAT_DARK),
        ]
    return geoms

def eyes():
    """The head lamps, small and near the face's outer edges, in black eye
    sockets: round round each lamp, narrowing inwards (flat ellipsoids) into
    the long thin LED bar that joins them (the face's centre line)."""
    x, z = FACE_X, 0.34
    geoms = []
    for name, sign in (("left", 1), ("right", -1)):
        geoms += [
            cylinder(f"eye_socket_{name}", (x - 0.015, sign * 0.40, z), (0.088, 0.025), BLACK, ALONG_X),
            ellipsoid(f"eye_socket_inner_{name}", (x - 0.015, sign * 0.30, z - 0.006), (0.025, 0.10, 0.042), BLACK),
            *round_lamp(f"head_lamp_{name}", x + 0.005, sign * 0.40, z, 0.068, LAMP, 1),
        ]
    geoms.append(box("led_bar_channel", (x + 0.002, 0, z - 0.008), (0.004, 0.23, 0.015), BLACK))
    geoms.append(box("led_bar", (x + 0.007, 0, z - 0.008), (0.004, 0.22, 0.007), LAMP))
    return geoms


def slanted_yz(name, a, b, x, half_x, half_thickness, outward, rgba):
    """A plate in the y-z plane (at x) whose edge runs from a (y, z) to b (y, z),
    lying on the side of it away from the car's centre line when `outward`."""
    (y0, z0), (y1, z1) = a, b
    angle = math.atan2(z1 - z0, y1 - y0)  # turning y about x onto the edge
    normal = (-math.sin(angle), math.cos(angle))
    side = 1 if (normal[0] * (y0 + y1) > 0) == outward else -1
    centre = (x, (y0 + y1) / 2 + side * half_thickness * normal[0], (z0 + z1) / 2 + side * half_thickness * normal[1])
    half_length = math.hypot(y1 - y0, z1 - z0) / 2
    return (f'      <geom name="{name}_visual" type="box" pos="{fmt(centre)}" '
            f'size="{fmt((half_x, half_length, half_thickness))}" euler="{angle:g} 0 0" rgba="{rgba}" {VISUAL}/>')


def bumper():
    """The bumper: dark grey, standing out ahead of the face (its top a ledge),
    a recess low in the middle. At each end it rises in a slant into the
    face's lower corner (the amber marker on it) and wraps round onto the side,
    running back down into the fender."""
    geoms = [
        *span("front_bumper", 1.33, 1.52, 0.62, -0.22, 0.04, 0.07, GREY),
        box("face_foot_shadow", (1.465, 0, 0.046), (0.006, 0.36, 0.006), BLACK),
        box("bumper_recess", (1.521, 0, -0.165), (0.004, 0.32, 0.045), SEAT_DARK),
        box("bumper_recess_edge", (1.522, 0, -0.118), (0.004, 0.32, 0.004), BLACK),
    ]
    for name, sign in (("left", 1), ("right", -1)):
        geoms += [
            # On the face: a slant from the bumper's top up into the corner, and the corner itself
            slanted_yz(f"bumper_wing_slant_{name}", (sign * 0.40, 0.04), (sign * 0.53, 0.27), 1.4725, 0.0275, 0.05, True, GREY),
            box(f"bumper_wing_{name}", (1.4725, sign * 0.57, 0.155), (0.0275, 0.04, 0.115), GREY),
            # Round the corner onto the side, its back edge slanting down into the fender
            box(f"bumper_wing_side_{name}", (1.43, sign * 0.612, 0.155), (0.07, 0.012, 0.115), GREY),
            slanted(f"bumper_wing_side_slant_{name}", (1.36, 0.27), (1.27, 0.10), sign * 0.612, 0.012, 0.05, -1, GREY),
            box(f"front_marker_{name}", (1.503, sign * 0.565, 0.15), (0.004, 0.012, 0.07), AMBER),
        ]
    return geoms

def fender(name, centre, radius, thickness, rgba, segments=8):
    """A wheel arch: capsules along a half circle above the wheel centre."""
    x, y, z = centre
    points = [(x + radius * math.cos(math.pi * step / segments), y, z + radius * math.sin(math.pi * step / segments))
              for step in range(segments + 1)]
    return [capsule(f"{name}_{index}", start, end, thickness, rgba) for index, (start, end) in enumerate(zip(points, points[1:]))]



def arch_band(name, centre, y, r_in, r_out, half_y, rgba, segments=24, a0=0.0, a1=math.pi):
    """A flat band (thin in y) round a wheel arch, from r_in to r_out about the
    wheel centre (x, z), from angle a0 (front) to a1 (back): boxes along it."""
    cx, cz = centre
    step = (a1 - a0) / segments
    middle = (r_in + r_out) / 2
    half_length = middle * math.tan(step / 2) + 0.002  # neighbours meet at the middle of the band
    geoms = []
    for index in range(segments):
        angle = a0 + step * (index + 0.5)
        # Every other piece a hair outwards, so that the overlaps do not flicker
        offset = 0.0006 * (index % 2) * (1 if y >= 0 else -1)
        pos = (cx + middle * math.cos(angle), y + offset, cz + middle * math.sin(angle))
        pitch = math.pi / 2 - angle  # the box's z along the radius
        geoms.append(box(f"{name}_{index}", pos, (half_length, half_y, (r_out - r_in) / 2), rgba, euler=f"0 {pitch:g} 0"))
    return geoms

def ring(name, centre, normal, radius, thickness, rgba, segments=12):
    """A torus-like ring of capsules (the steering wheel) around `normal`."""
    nx, ny, nz = normal
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    n = (nx / length, ny / length, nz / length)
    u = (0.0, 1.0, 0.0)  # the normal is in the x-z plane, so y lies in the ring
    v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0])
    points = []
    for step in range(segments + 1):
        angle = 2 * math.pi * step / segments
        c, s = math.cos(angle) * radius, math.sin(angle) * radius
        points.append(tuple(centre[i] + c * u[i] + s * v[i] for i in range(3)))
    return [capsule(f"{name}_{index}", start, end, thickness, rgba) for index, (start, end) in enumerate(zip(points, points[1:]))]


def both(make, name, y, *rest):
    """A left (+y) and a right (-y) copy: make(name, y, *rest) -> geom or list of geoms."""
    geoms = []
    for side, sign in (("left", 1), ("right", -1)):
        made = make(f"{name}_{side}", sign * y, *rest)
        geoms.extend(made if isinstance(made, list) else [made])
    return geoms


def round_lamp(name, x, y, z, radius, ring_rgba, facing):
    """A round lamp on a face at x: a glowing ring, a dark inside and a lens (facing +1 front, -1 back)."""
    return [
        cylinder(f"{name}_ring", (x, y, z), (radius, 0.010), ring_rgba, ALONG_X),
        cylinder(f"{name}_inside", (x + facing * 0.004, y, z), (radius * 0.82, 0.010), BLACK, ALONG_X),
        cylinder(f"{name}_lens", (x + facing * 0.008, y, z), (radius * 0.38, 0.010), LENS, ALONG_X),
    ]


BACK_RECLINE = math.radians(15)  # the backrests lean back this much


def seat(name, x, y, z):
    """One seat facing forward: a dark base, a cushion and a backrest leaning
    back BACK_RECLINE about its foot (at the cushion's back), with an orange
    line down its front."""
    pitch = -BACK_RECLINE  # MuJoCo's pitch: negative leans the top backwards
    up = (math.sin(pitch), math.cos(pitch))       # along the backrest, upwards
    forward = (math.cos(pitch), -math.sin(pitch))  # out of its front face
    foot = (x - 0.23, z + 0.05)  # the backrest's foot, behind the cushion

    def along(height, depth=0.0):  # a point `height` up the backrest and `depth` out of its middle plane
        return (foot[0] + height * up[0] + depth * forward[0], foot[1] + height * up[1] + depth * forward[1])

    euler = f"0 {pitch:g} 0"
    back_x, back_z = along(0.27)
    frame_x, frame_z = along(0.25, -0.03)
    line_x, line_z = along(0.29, 0.051)
    return [
        box(f"{name}_base", (x, y, z - 0.08), (0.20, 0.22, 0.03), SEAT_DARK),
        *rounded_box(f"{name}_cushion", (x, y, z), (0.22, 0.23, 0.06), 0.05, SEAT),
        *rounded_box(f"{name}_back", (back_x, y, back_z), (0.05, 0.22, 0.27), 0.04, SEAT, pitch=pitch),
        box(f"{name}_back_frame", (frame_x, y, frame_z), (0.03, 0.23, 0.28), SEAT_DARK, euler=euler),
        box(f"{name}_back_line", (line_x, y + (0.11 if y > 0 else -0.11), line_z), (0.004, 0.012, 0.20), ORANGE, euler=euler),
    ]


def armrest(name, y, x, z):
    """An armrest on the outer side of a row: a bar and its post."""
    return [
        capsule(f"{name}_bar", (x + 0.16, y, z + 0.22), (x - 0.20, y, z + 0.22), 0.025, BLACK),
        capsule(f"{name}_post", (x + 0.16, y, z + 0.22), (x + 0.16, y, z), 0.022, BLACK),
    ]


def steering_wheel():
    column_base, column_top = (0.96, SEAT_Y, 0.66), (0.72, SEAT_Y, 0.92)
    axis = tuple(column_top[i] - column_base[i] for i in range(3))
    return [
        capsule("steering_column", column_base, column_top, 0.028, BLACK),
        *ring("steering_wheel", column_top, axis, 0.17, 0.018, BLACK),
        capsule("steering_spoke", (column_top[0], SEAT_Y - 0.16, column_top[2]), (column_top[0], SEAT_Y + 0.16, column_top[2]), 0.014, BLACK),
    ]


def mirror(name, y):
    sign = 1 if y > 0 else -1
    return [
        capsule(f"{name}_arm", (1.00, sign * 0.60, 1.05), (1.00, y, 1.05), 0.012, BLACK),
        box(f"{name}_head", (1.00, y + sign * 0.02, 1.10), (0.02, 0.045, 0.085), BLACK),
        box(f"{name}_signal", (1.022, y + sign * 0.02, 1.10), (0.003, 0.010, 0.060), AMBER),
    ]


BODY = [
    "      <!-- Under the floor: the floor, the sills (white, an orange line) and the dark blocks between the wheels -->",
    box("floor", (0, 0, -0.12), (0.80, 0.57, 0.02), SEAT_DARK),
    *both(lambda n, y: rounded_box(n, (0, y, -0.12), (0.78, 0.04, 0.06), 0.03, WHITE), "sill", 0.585),
    *both(lambda n, y: box(n, (0.30, y, -0.13), (0.30, 0.004, 0.010), ORANGE), "sill_line_front", 0.627),
    *both(lambda n, y: box(n, (-0.40, y, -0.13), (0.28, 0.004, 0.010), ORANGE), "sill_line_rear", 0.627),
    box("front_underbody", (WHEEL_X, 0, -0.01), (0.26, 0.38, 0.13), GREY),
    box("rear_underbody", (-WHEEL_X, 0, -0.01), (0.26, 0.38, 0.13), GREY),
    # The front fenders: wide dark grey bands along the arches, standing out a little; the rear arches under the rear body
    *(geom for side, y in (("left", 0.61), ("right", -0.61))
      for geom in arch_band(f"fender_front_{side}", (WHEEL_X, WHEEL_Z), y, 0.29, 0.37, 0.025, GREY)),
    *(geom for side, y in (("left", 0.60), ("right", -0.60))
      for geom in fender(f"arch_rear_{side}", (-WHEEL_X, y, WHEEL_Z), 0.31, 0.035, GREY)),

    "      <!-- The front: a black cowl, a white face (black eye sockets, LED bar) and a dark grey bumper; the sides flow down to the wheel arches -->",
    *nose(),
    *eyes(),
    *bumper(),
    "      <!-- The windshield's foot on the cowl, the dashboard behind it, the steering wheel (the driver sits on the left) -->",
    capsule("windshield_foot", (1.10, -0.58, 0.60), (1.10, 0.58, 0.60), 0.022, BLACK),
    *span("dashboard", 0.90, 1.08, 0.58, 0.56, 0.72, 0.06, SEAT_DARK),
    *steering_wheel(),

    "      <!-- Seats: the front row on a white pedestal, the rear row on the rear body -->",
    *span("front_pedestal", -0.05, 0.45, 0.56, -0.12, 0.28, 0.06, WHITE),
    *both(lambda n, y: seat(n, FRONT_ROW_X, y, 0.36), "front_seat", SEAT_Y),
    *both(lambda n, y: armrest(n, y, FRONT_ROW_X, 0.36), "front_armrest", 0.54),
    *span("rear_body", -1.62, -0.78, 0.62, 0.12, 0.30, 0.06, WHITE),
    *span("tail", -1.62, -1.26, 0.62, 0.12, 0.52, 0.10, WHITE),
    *both(lambda n, y: seat(n, REAR_ROW_X, y, 0.36), "rear_seat", SEAT_Y),
    *both(lambda n, y: armrest(n, y, REAR_ROW_X, 0.36), "rear_armrest", 0.54),
    "      <!-- The grab bar behind the rear row -->",
    capsule("grab_bar_top", (-1.54, -0.52, 0.90), (-1.54, 0.52, 0.90), 0.022, BLACK),
    *both(lambda n, y: capsule(n, (-1.54, y, 0.90), (-1.54, y, 0.52), 0.022, BLACK), "grab_bar_post", 0.52),
    *both(lambda n, y: capsule(n, (-1.54, y, 0.90), (-1.30, y, 0.90), 0.020, BLACK), "grab_bar_side", 0.56),

    "      <!-- The back: a dark bumper, round red tail lamps and a red bar -->",
    *span("rear_bumper", -1.63, -1.30, 0.58, -0.20, 0.13, 0.09, GREY),
    *round_lamp("tail_lamp_left", -1.625, 0.38, 0.32, 0.07, RED, -1),
    *round_lamp("tail_lamp_right", -1.625, -0.38, 0.32, 0.07, RED, -1),
    box("tail_bar", (-1.623, 0, 0.31), (0.006, 0.28, 0.010), RED),
    *both(lambda n, y: box(n, (-1.635, y, -0.02), (0.006, 0.012, 0.06), AMBER), "rear_marker", 0.45),

    "      <!-- The roof: black pillars, an open windshield frame, a long white roof with orange lines -->",
    *both(lambda n, y: capsule(n, (1.12, y, 0.58), (0.76, y, 1.92), 0.035, BLACK), "front_pillar", 0.58),
    *both(lambda n, y: capsule(n, (-1.50, y, 0.52), (-1.50, y, 1.92), 0.035, BLACK), "rear_pillar", 0.58),
    capsule("windshield_top", (0.78, -0.58, 1.86), (0.78, 0.58, 1.86), 0.025, BLACK),
    *both(mirror, "mirror", 0.70),
    *span("roof", -1.74, 0.96, 0.68, 1.92, 2.04, 0.05, WHITE),
    box("roof_underside", (-0.39, 0, 1.915), (1.30, 0.62, 0.006), UNDER_ROOF),
    *both(lambda n, y: box(n, (-0.39, y, 1.985), (1.10, 0.004, 0.010), ORANGE), "roof_line", 0.682),
    box("roof_front_line", (0.962, 0, 1.985), (0.004, 0.50, 0.010), ORANGE),
]


def wheel(name, indent):
    return "\n".join([
        cylinder(f"{name}_tire", (0, 0, 0), (WHEEL_R, 0.10), TIRE, ALONG_Y, indent),
        cylinder(f"{name}_rim", (0, 0, 0), (0.17, 0.102), RIM, ALONG_Y, indent),
        cylinder(f"{name}_spokes", (0, 0, 0), (0.13, 0.104), SILVER, ALONG_Y, indent),
        cylinder(f"{name}_cap", (0, 0, 0), (0.035, 0.106), ORANGE, ALONG_Y, indent),
    ])


def steered(side, y):
    return f'''      <body name="front_{side}_steer" pos="{WHEEL_X:g} {y:g} {WHEEL_Z:g}">
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
    return f'''      <body name="rear_{side}_wheel" pos="{-WHEEL_X:g} {y:g} {WHEEL_Z:g}">
        <joint name="rear_{side}_wheel_joint" type="hinge" axis="0 1 0"
               damping="0.05" armature="0.01"/>
{wheel(f"rear_{side}", "        ")}
      </body>'''


def model() -> str:
    return f'''<mujoco model="hakoniwa_cart">
  <compiler angle="radian" autolimits="true"/>

  <!--
    Hakoniwa Cart: a four-seat cart authored for Hakoniwa from boxes,
    cylinders and capsules (a rounded white nose with round head lamps, two
    rows of seats, a long roof). Written by build_model.py: change it there.
    Every geom here is visual only (group 1, no contact, no mass). Physical
    collision geoms and mass, actuators, contact excludes, and the world are
    injected from the sibling YAML files by tools/ackermann/forge.py.
    The vehicle frame is 0.45 m above the ground (the wheel centres 0.27 m).
  -->
  <worldbody>
    <body name="vehicle">
{chr(10).join(BODY)}

{steered("left", WHEEL_Y)}

{steered("right", -WHEEL_Y)}

{driven("left", WHEEL_Y)}

{driven("right", -WHEEL_Y)}
    </body>
  </worldbody>
</mujoco>
'''


if __name__ == "__main__":
    target = Path(__file__).with_name("model.xml")
    target.write_text(model(), encoding="utf-8")
    print(f"Wrote {target}")
