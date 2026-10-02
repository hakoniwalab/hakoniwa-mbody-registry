#!/usr/bin/env python3
"""Write model.<variant>.xml: the 箱庭人間 (Hakoniwa People), and generate
their GLB parts and view models.

In MuJoCo a person is a stick: one capsule that slides on x and y and turns
about z, a little above the ground (no gravity on it, no feet; it bumps into
walls, cars and other people). The arms and legs are bodies on hinges
(shoulders, hips) held straight by soft springs; a walk is an animation of
those joint angles, not dynamics. Every visual geom is a MuJoCo primitive;
heads, bodies and hair are rounded boxes (three boxes and twelve edge
capsules, as the Hakoniwa Car).

  python bodies/hakoniwa_person/config/build_model.py          # model.<variant>.xml
  python bodies/hakoniwa_person/config/build_model.py --generate  # + generated/<variant>/
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG = Path(__file__).resolve().parent
BODY = CONFIG.parent
REPO = BODY.parents[1]

SKIN = "0.98 0.84 0.70 1"
HAIR = "0.36 0.23 0.15 1"
EYE = "0.10 0.10 0.11 1"
WHITE = "0.94 0.94 0.93 1"
ORANGE = "0.95 0.42 0.11 1"
DARK = "0.20 0.21 0.24 1"
SHOE = "0.12 0.12 0.13 1"
BLUE = "0.20 0.40 0.70 1"
KHAKI = "0.66 0.56 0.40 1"
GREEN = "0.42 0.72 0.27 1"
YELLOW = "0.98 0.80 0.12 1"
LIGHT_BLUE = "0.45 0.62 0.85 1"
VISUAL = 'contype="0" conaffinity="0" density="0" group="1"'


def fmt(values) -> str:
    return " ".join(f"{value:g}" for value in values)


def box(name, pos, size, rgba):
    return f'<geom name="{name}_visual" type="box" pos="{fmt(pos)}" size="{fmt(size)}" rgba="{rgba}" {VISUAL}/>'


def cylinder(name, pos, size, rgba):
    return f'<geom name="{name}_visual" type="cylinder" pos="{fmt(pos)}" size="{fmt(size)}" rgba="{rgba}" {VISUAL}/>'


def rounded_box(name, pos, size, radius, rgba):
    """A box with its edges and corners rounded by `radius`."""
    (x, y, z), (a, b, c), r = pos, size, radius
    if not 0 < r <= min(size):
        raise ValueError(f"{name}: radius {r} must be within (0, {min(size)}]")
    geoms = [box(f"{name}_x", pos, (a, b - r, c - r), rgba), box(f"{name}_y", pos, (a - r, b, c - r), rgba),
             box(f"{name}_z", pos, (a - r, b - r, c), rgba)]
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
                    start[index] += sign * (half[index] - r)
                    end[index] += sign * (half[index] - r)
                geoms.append(f'<geom name="{name}_edge{number}_visual" type="capsule" fromto="{fmt(start + end)}" '
                             f'size="{r:g}" rgba="{rgba}" {VISUAL}/>')
                number += 1
    return geoms


@dataclass(frozen=True)
class Look:
    """What a person wears; sizes are an adult's, scaled for a child."""

    title: str
    shirt: str
    sleeve: str
    pants: str
    scale: float = 1.0
    shorts: bool = False
    hat: str | None = None          # "cap" or "round"
    hat_colour: str = WHITE
    brim_colour: str = ORANGE
    front: str | None = None        # "tie", "apron", "vest"
    front_colour: str = ORANGE
    backpack: bool = False


LOOKS = {
    "visitor": Look("立ち客", shirt=WHITE, sleeve=WHITE, pants=DARK, front="tie"),
    "staff": Look("店員", shirt=WHITE, sleeve=WHITE, pants=DARK, hat="cap", front="apron"),
    "passerby": Look("通行人", shirt=WHITE, sleeve=WHITE, pants=KHAKI, hat="cap", hat_colour=BLUE, brim_colour=BLUE,
                     front="vest", front_colour=BLUE, backpack=True),
    "child": Look("子ども", shirt=GREEN, sleeve=GREEN, pants=KHAKI, scale=0.7, shorts=True, hat="round",
                  hat_colour=YELLOW, brim_colour=YELLOW),
}

# Joint and body names every variant shares (the viewer and the runtime use them).
LIMB_JOINTS = ("shoulder_left_joint", "shoulder_right_joint", "hip_left_joint", "hip_right_joint")


def model(variant: str, look: Look) -> str:
    s = look.scale
    head_s = s ** 0.6  # a child's head is relatively bigger

    def v(*values):
        return tuple(value * s for value in values)

    def h(*values):
        return tuple(value * head_s for value in values)

    hip_z, shoulder_z, neck_z = 0.66 * s, 1.10 * s, 1.14 * s
    torso = [*rounded_box("torso", v(0, 0, 0.24), v(0.12, 0.20, 0.25), 0.035 * s, look.shirt)]
    if look.front == "tie":
        torso += [box("shirt_front", v(0.122, 0, 0.27), v(0.005, 0.05, 0.21), ORANGE)]
    elif look.front == "apron":
        torso += [box("apron", v(0.13, 0, 0.16), v(0.008, 0.17, 0.25), look.front_colour),
                  box("apron_bib", v(0.13, 0, 0.42), v(0.008, 0.11, 0.06), look.front_colour),
                  box("apron_mark", v(0.139, 0, 0.17), v(0.002, 0.05, 0.04), WHITE),
                  box("apron_mark_roof", v(0.139, 0, 0.225), v(0.002, 0.035, 0.018), WHITE),
                  box("apron_mark_window", v(0.141, 0, 0.165), v(0.002, 0.02, 0.02), look.front_colour)]
        torso += [box(f"apron_tie_{side}", v(0, sign * 0.205, 0.18), v(0.10, 0.006, 0.015), look.front_colour)
                  for side, sign in (("left", 1), ("right", -1))]
    elif look.front == "vest":
        torso += [box(f"vest_{side}", v(0.124, sign * 0.12, 0.24), v(0.008, 0.08, 0.24), look.front_colour)
                  for side, sign in (("left", 1), ("right", -1))]
        torso += [box("vest_back", v(-0.124, 0, 0.24), v(0.008, 0.2, 0.24), look.front_colour)]
    if look.backpack:
        torso += [*rounded_box("backpack", v(-0.20, 0, 0.27), v(0.08, 0.16, 0.19), 0.03 * s, DARK)]
        torso += [box(f"backpack_strap_{side}", v(0.125, sign * 0.13, 0.30), v(0.006, 0.025, 0.2), DARK)
                  for side, sign in (("left", 1), ("right", -1))]

    head = [*rounded_box("head", h(0, 0, 0.19), h(0.19, 0.19, 0.18), 0.045 * head_s, SKIN)]
    head += [box(f"eye_{side}", h(0.192, sign * 0.075, 0.18), h(0.004, 0.026, 0.045), EYE)
             for side, sign in (("left", 1), ("right", -1))]
    head += [*rounded_box("hair_top", h(-0.01, 0, 0.35), h(0.205, 0.205, 0.06), 0.035 * head_s, HAIR),
             box("hair_back", h(-0.18, 0, 0.24), h(0.03, 0.2, 0.13), HAIR),
             box("hair_fringe", h(0.17, 0, 0.32), h(0.04, 0.2, 0.04), HAIR)]
    head += [box(f"hair_side_{side}", h(-0.06, sign * 0.19, 0.27), h(0.12, 0.018, 0.08), HAIR)
             for side, sign in (("left", 1), ("right", -1))]
    if look.hat == "cap":
        head += [*rounded_box("cap", h(-0.005, 0, 0.385), h(0.21, 0.21, 0.07), 0.04 * head_s, look.hat_colour),
                 box("cap_front", h(0.206, 0, 0.385), h(0.006, 0.12, 0.05), look.brim_colour),
                 box("cap_brim", h(0.28, 0, 0.33), h(0.09, 0.17, 0.012), look.brim_colour)]
        if look.hat_colour == WHITE:
            head += [box("cap_mark", h(0.213, 0, 0.385), h(0.002, 0.04, 0.03), WHITE)]
    elif look.hat == "round":
        head += [cylinder("hat_brim", h(0, 0, 0.34), h(0.27, 0.012), look.brim_colour),
                 *rounded_box("hat_crown", h(0, 0, 0.42), h(0.18, 0.18, 0.08), 0.06 * head_s, look.hat_colour)]

    def arm(side, sign):
        geoms = [*rounded_box(f"arm_{side}", v(0, 0, -0.18), v(0.065, 0.065, 0.2), 0.025 * s, look.sleeve),
                 *rounded_box(f"hand_{side}", v(0, 0, -0.43), v(0.058, 0.058, 0.055), 0.025 * s, SKIN)]
        return body(f"arm_{side}", v(0, sign * 0.27, shoulder_z / s), f"shoulder_{side}_joint", "0 1 0",
                    "-75 75", geoms)

    def leg(side, sign):
        if look.shorts:
            geoms = [box(f"shorts_{side}", v(0, 0, -0.12), v(0.085, 0.09, 0.12), look.pants),
                     box(f"shin_{side}", v(0, 0, -0.40), v(0.07, 0.075, 0.18), SKIN)]
        else:
            geoms = [box(f"leg_{side}", v(0, 0, -0.32), v(0.08, 0.085, 0.26), look.pants)]
        geoms += [*rounded_box(f"shoe_{side}", v(0.025, 0, -0.62), v(0.11, 0.09, 0.04), 0.02 * s, SHOE)]
        return body(f"leg_{side}", v(0, sign * 0.105, hip_z / s), f"hip_{side}_joint", "0 1 0", "-100 60", geoms)

    radius = 0.22 * s
    lines = [
        f'<mujoco model="hakoniwa_person_{variant}">',
        '  <compiler angle="degree"/>',
        "  <worldbody>",
        f"    <!-- {look.title}: a stick that slides and turns; limbs are animated -->",
        '    <body name="person" pos="0 0 0">',
        '      <joint name="slide_x_joint" type="slide" axis="1 0 0" damping="20"/>',
        '      <joint name="slide_y_joint" type="slide" axis="0 1 0" damping="20"/>',
        '      <joint name="turn_joint" type="hinge" axis="0 0 1" damping="5"/>',
        f'      <geom name="person_collision" type="capsule" fromto="0 0 {0.05 * s + radius:g} 0 0 {1.58 * s - radius:g}" '
        f'size="{radius:g}" mass="{60 * s ** 3:g}" group="3" rgba="0.2 0.6 1 0"/>',
        "      <!-- A round shadow under the feet (the stick's own part in the viewer) -->",
        "      " + cylinder("shadow", (0, 0, 0.004), (0.24 * s, 0.002), "0.32 0.33 0.36 1"),
        *body("torso", (0, 0, hip_z), None, None, None, torso, indent=6, children=[
            body("head", (0, 0, neck_z - hip_z), None, None, None, head, indent=8)]),
        *arm("left", 1), *arm("right", -1), *leg("left", 1), *leg("right", -1),
        "    </body>",
        "  </worldbody>",
        "  <actuator>",
        '    <velocity name="move_x" joint="slide_x_joint" kv="400" ctrlrange="-3 3" forcerange="-150 150" forcelimited="true"/>',
        '    <velocity name="move_y" joint="slide_y_joint" kv="400" ctrlrange="-3 3" forcerange="-150 150" forcelimited="true"/>',
        '    <velocity name="turn" joint="turn_joint" kv="60" ctrlrange="-3.14 3.14" forcerange="-40 40" forcelimited="true"/>',
        "  </actuator>",
        "</mujoco>",
    ]
    return "\n".join(flatten(lines)) + "\n"


def body(name, pos, joint, axis, limits, geoms, indent=6, children=()):
    pad = " " * indent
    lines = [f'{pad}<body name="{name}" pos="{fmt(pos)}">']
    if joint:
        lines += [f'{pad}  <joint name="{joint}" type="hinge" axis="{axis}" range="{limits}" limited="true" '
                  f'stiffness="40" damping="4"/>',
                  f'{pad}  <inertial pos="0 0 -0.25" mass="0.5" diaginertia="0.01 0.01 0.002"/>']
    lines += [f"{pad}  {geom}" for geom in geoms]
    for child in children:
        lines += child
    lines.append(f"{pad}</body>")
    return lines


def flatten(lines):
    for line in lines:
        if isinstance(line, list):
            yield from flatten(line)
        else:
            yield line


def generate(variant: str, source: Path) -> None:
    """generated/<variant>/: the MJCF, its parts GLB (one per body) and view model."""
    out = BODY / "generated" / variant
    if out.exists():
        shutil.rmtree(out)
    (out / "parts").mkdir(parents=True)
    shutil.copyfile(source, out / "model.xml")
    run("mjcf2glb.py", out / "model.xml", "--output-dir", out / "parts", "--split-by", "body", "--capsule-count", "12",
        "--visible-only")
    recipe = out / "viewer.recipe.yaml"
    recipe.write_text(
        "format: hako_viewer_model_recipe\nversion: 0.1\n\n"
        f"robot: hakoniwa_person_{variant}\nmjcf: model.xml\ncoordinate_system: mujoco\n\n"
        "assets:\n  glb_dir: parts\n  map: body_name\n\nbase: person\n\nmovable_joints:\n"
        + "".join(f"  - {joint}\n" for joint in LIMB_JOINTS), encoding="utf-8")
    run("hako_viewer_model_gen.py", recipe, "--out", out / "view-model.json", "--pretty")


def run(tool: str, *args) -> None:
    subprocess.run([sys.executable, str(REPO / "tools" / tool), *(str(arg) for arg in args)], cwd=REPO, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--generate", action="store_true", help="also write generated/<variant>/")
    args = parser.parse_args()
    for variant, look in LOOKS.items():
        path = CONFIG / f"model.{variant}.xml"
        path.write_text(model(variant, look), encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}")
        if args.generate:
            generate(variant, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
