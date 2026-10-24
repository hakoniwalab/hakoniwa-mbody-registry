#!/usr/bin/env python3
"""The visual body of Hakoniwa Car 2 as lofted meshes (one mesh per material).

The body is a loft of cross sections along x (the vehicle frame: x forward,
y left, z up, wheel centres at z = 0, the ground at z = -0.31). Each section
is the right half of the outline (bottom centre -> side -> greenhouse -> roof
centre); the left half mirrors it. A side profile (top and bottom), a belt
line, a plan width and a tumblehome give the shape of a modern five-door
hatchback (docs: hakoniwa-scenario-pro docs/requests/img/car2-reference.webp):
a short hood falling to the nose, a raked windshield, a roof highest over the
front seats, a steep rear hatch, wheel arches cut out of the side.

Each quad of the loft goes to one material by where it is (glass for the
windows, black for pillars, seams, cladding and the underside, paint for the
rest). Paint and black also get an inner shell (reversed, 4 mm inside) so the
pillars and the roof are seen from the driver's seat. Only the visual changes:
collision stays the primitives of collision_primitives.yaml.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

GROUND = -0.31
X_FRONT, X_REAR = 2.19, -2.19
WHEEL_X = (1.30, -1.30)
ARCH_R = 0.385                     # wheel arch radius (tyre 0.31 + 0.065 gap)
HALF_W = 0.89                      # body half width (1.78 m)

# Side profile, top: (x, z), front to rear. Read off the reference's left side
# view (car2-reference.webp): a fairly upright nose, a hood rising to a high
# cowl, a raked windshield, a gently arched roof, a raked hatch glass under a
# small spoiler, a short vertical tail.
TOP = [
    (2.19, 0.08), (2.188, 0.22), (2.17, 0.33), (2.13, 0.415), (2.06, 0.475),   # rounded nose
    (1.90, 0.525), (1.60, 0.580), (1.30, 0.625), (1.05, 0.660), (0.88, 0.690),  # hood to cowl
    (0.65, 0.800), (0.45, 0.920), (0.30, 1.020), (0.20, 1.085), (0.10, 1.130),  # windshield
    (-0.10, 1.180), (-0.35, 1.205), (-0.70, 1.205), (-1.05, 1.192), (-1.40, 1.170),  # long arched roof
    (-1.62, 1.150), (-1.74, 1.140), (-1.78, 1.128),                             # spoiler lip
    (-1.83, 1.06), (-1.90, 0.95), (-1.97, 0.83), (-2.01, 0.76),                # raked hatch glass
    (-2.07, 0.68), (-2.13, 0.60), (-2.17, 0.47), (-2.19, 0.32), (-2.19, 0.10),  # tail, bumper
]
X_COWL, X_ROOF_FRONT = 0.88, 0.10
X_SPOILER, X_HATCH_GLASS_LOW = -1.78, -2.01
# The belt (window sill) is high and rises to the rear, as in the reference.
BELT = [(0.88, 0.615), (0.55, 0.625), (0.0, 0.645), (-0.80, 0.675), (-1.30, 0.705), (-2.01, 0.75)]
# Door seams and pillars (x).
SEAMS = (0.92, -0.39, -1.34)       # front door front edge, B (door/door), rear door rear edge
B_PILLAR = (-0.43, -0.35)
C_PILLAR = (-1.80, -1.28)


def interp(points, x):
    xs = [p[0] for p in points][::-1]
    zs = [p[1] for p in points][::-1]
    return float(np.interp(x, xs, zs))


def z_top(x):
    return interp(TOP, x)


def z_belt(x):
    return interp(BELT, min(max(x, BELT[-1][0]), BELT[0][0]))


def z_bottom(x):
    base = -0.115
    if x > 1.85:   # the front bumper's lower edge rises to the nose
        base = -0.115 + (x - 1.85) / (X_FRONT - 1.85) * 0.09
    if x < -1.95:  # the rear bumper's lower edge
        base = -0.115 + (-1.95 - x) / (-1.95 - X_REAR) * 0.08
    for wx in WHEEL_X:
        dx = x - wx
        if abs(dx) < ARCH_R:
            base = max(base, math.sqrt(ARCH_R * ARCH_R - dx * dx))
    return base


def plan_half_width(x):
    """The plan outline: straight sides, rounded front and rear corners."""
    r_front, r_rear = 0.46, 0.30
    if x > X_FRONT - r_front:
        d = x - (X_FRONT - r_front)
        return HALF_W - r_front + math.sqrt(max(r_front * r_front - d * d, 0.0))
    if x < X_REAR + r_rear:
        d = (X_REAR + r_rear) - x
        return HALF_W - r_rear + math.sqrt(max(r_rear * r_rear - d * d, 0.0))
    return HALF_W


def side_half_width(x, z):
    """The lower body: fullest at the shoulder (z = 0.30), tucked in below."""
    b = plan_half_width(x)
    t = (z - 0.42) / 0.55
    w = b * (1.0 - 0.05 * t * t)
    for wx in WHEEL_X:                      # fender flares around the wheel arches
        d = abs(x - wx)
        if d < 0.62 and z < 0.62:
            w += 0.018 * (1 - d / 0.62) * min(1.0, (0.62 - z) / 0.25)
    return min(w, HALF_W)


def has_greenhouse(x):
    return X_HATCH_GLASS_LOW <= x <= X_COWL


ROOF_HALF = 0.64          # roof half width (tumblehome from the belt)
N_BOTTOM, N_LOWER, N_GREEN, N_ROUND, N_ROOF = 4, 10, 7, 4, 6
R_BOTTOM, R_ROOF = 0.06, 0.07


def section(x):
    """The right half of the outline at x: points (y, z) and a segment tag each."""
    zb, zt = z_bottom(x), z_top(x)
    green = has_greenhouse(x) and z_belt(x) < zt - R_ROOF - 0.02
    zbelt = z_belt(x) if green else zt - R_ROOF
    zbelt = max(zbelt, zb + R_BOTTOM + 0.01)
    pts, tags = [], []
    hw_b = side_half_width(x, zb + R_BOTTOM)
    for i in range(N_BOTTOM):                      # bottom, centre outwards
        y = (hw_b - R_BOTTOM) * i / N_BOTTOM
        pts.append((y, zb)); tags.append("bottom")
    for i in range(N_BOTTOM):                      # bottom outer rounding
        a = -math.pi / 2 + (math.pi / 2) * i / N_BOTTOM
        pts.append((hw_b - R_BOTTOM + R_BOTTOM * math.cos(a), zb + R_BOTTOM + R_BOTTOM * math.sin(a)))
        tags.append("bottom")
    z0 = zb + R_BOTTOM
    for i in range(N_LOWER + 1):                   # lower side up to the belt
        z = z0 + (zbelt - z0) * i / N_LOWER
        pts.append((side_half_width(x, z), z)); tags.append("lower")
    hw_belt = side_half_width(x, zbelt) - 0.025    # a small shoulder step at the belt
    roof_half = ROOF_HALF * min(1.0, plan_half_width(x) / HALF_W)
    if green:
        z_roof_edge = zt - R_ROOF
        for i in range(N_GREEN + 1):               # greenhouse side (tumblehome)
            t = i / N_GREEN
            pts.append((hw_belt + (roof_half + R_ROOF * 0.3 - hw_belt) * t, zbelt + (z_roof_edge - zbelt) * t))
            tags.append("green")
        y_edge = roof_half + R_ROOF * 0.3
    else:
        for i in range(N_GREEN + 1):               # collapsed: no greenhouse here
            pts.append((hw_belt, zbelt)); tags.append("green")
        y_edge = hw_belt
    z_edge = zt - R_ROOF
    for i in range(1, N_ROUND + 1):                # roof (or hood) edge rounding
        a = (math.pi / 2) * i / N_ROUND
        pts.append((y_edge - R_ROOF + R_ROOF * math.cos(a) , z_edge + R_ROOF * math.sin(a)))
        tags.append("round")
    y_top = y_edge - R_ROOF
    for i in range(1, N_ROOF + 1):                 # top, outwards -> centre, with a crown
        y = y_top * (1 - i / N_ROOF)
        crown = 0.025 * (1 - (y / max(y_top, 1e-6)) ** 2)
        pts.append((y, zt + crown)); tags.append("top")
    return pts, tags


def stations():
    xs = set(np.round(np.linspace(X_REAR, X_FRONT, 141), 4))
    for s in SEAMS:
        xs.update((round(s - 0.006, 4), round(s + 0.006, 4)))
    for a, b in (B_PILLAR, C_PILLAR):
        xs.update((a, b))
    for x in (X_COWL, X_ROOF_FRONT, X_SPOILER, X_HATCH_GLASS_LOW):
        xs.add(x)
    for wx in WHEEL_X:
        xs.update(np.round(wx + ARCH_R * np.linspace(-1, 1, 25), 4))
    return sorted(xs)


def classify(tag, x, z, y):
    """The material of a quad by where it is."""
    if tag == "bottom":
        return "black_matte"
    if tag == "lower":
        if z < -0.07:
            return "black_matte"                       # rocker cladding / lower bumper
        if any(abs(x - s) < 0.006 for s in SEAMS) and z < z_belt(x) - 0.01 and z > -0.06:
            return "black_matte"                       # door seams
        return "body_paint"
    if tag == "green":
        if not has_greenhouse(x):
            return "body_paint"
        top = z_top(x) - R_ROOF
        if z > top - 0.02:
            return "body_paint"                        # drip rail under the roof edge
        if B_PILLAR[0] <= x <= B_PILLAR[1]:
            return "black_matte"
        if C_PILLAR[0] <= x <= C_PILLAR[1] or x < C_PILLAR[0] and x > X_HATCH_GLASS_LOW + 0.02:
            return "body_paint"                        # C pillar and the hatch side
        if x > X_COWL - 0.06:
            return "body_paint"                        # A pillar root at the cowl
        if z < z_belt(x) + 0.02:
            return "black_matte"                       # window seal at the belt
        return "glass"
    # round / top
    upper = tag == "top" or z > z_top(x) - 0.025      # the upper half of the edge rounding
    if X_ROOF_FRONT < x < X_COWL - 0.03:               # windshield; the A pillar is the lower rounding
        return "glass" if upper else "body_paint"
    if X_HATCH_GLASS_LOW + 0.02 < x < X_SPOILER - 0.03:  # rear hatch glass
        return "glass" if (tag == "top" and y < ROOF_HALF - 0.08) else "body_paint"
    return "body_paint"


def build(out_dir: Path) -> dict[str, Path]:
    xs = stations()
    sections = [section(x) for x in xs]
    n = len(sections[0][0])
    tris: dict[str, list] = {}

    inner_tris: dict[str, list] = {}

    cap_dir: dict = {}

    def add(material, a, b, c, inner=False, cap=0.0):
        tris.setdefault(material, []).append((a, b, c))
        if cap:
            cap_dir[tuple(np.round(np.mean(np.asarray((a, b, c)), axis=0), 4))] = cap
        if inner:
            inner_tris.setdefault(material, []).append((a, b, c))

    def p3(i, j, side):
        y, z = sections[i][0][j]
        return (xs[i], side * y, z)

    for i in range(len(xs) - 1):
        xm = 0.5 * (xs[i] + xs[i + 1])
        for j in range(n - 1):
            tag = sections[i][1][j + 1]
            ym = 0.5 * (sections[i][0][j][0] + sections[i][0][j + 1][0])
            zm = 0.5 * (sections[i][0][j][1] + sections[i][0][j + 1][1])
            material = classify(tag, xm, zm, ym)
            for side in (1, -1):
                a, b = p3(i, j, side), p3(i + 1, j, side)
                c, d = p3(i + 1, j + 1, side), p3(i, j + 1, side)
                inner = tag in ("green", "round", "top") and has_greenhouse(xm) and material != "glass"
                # Wound outwards by construction (x up the stations, j up the outline):
                # (a, c, b) faces +y on the right; the mirror flips it for the left.
                if side > 0:
                    add(material, a, c, b, inner); add(material, a, d, c, inner)
                else:
                    add(material, a, b, c, inner); add(material, a, c, d, inner)
    # End caps (front and rear faces), as fans from the centre of the section.
    for i, material, cap in ((0, "body_paint", -1.0), (len(xs) - 1, "body_paint", 1.0)):
        pts = sections[i][0]
        ring = [(xs[i], y, z) for y, z in pts] + [(xs[i], -y, z) for y, z in reversed(pts)]
        cx = (xs[i], 0.0, 0.5 * (pts[0][1] + pts[-1][1]))
        for k in range(len(ring) - 1):
            add(material, cx, ring[k], ring[k + 1], cap=cap)

    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for material, faces in tris.items():
        v = np.asarray(faces, dtype=float).reshape(-1, 3)
        f = np.arange(len(v)).reshape(-1, 3)
        # Orient every face outwards (away from the body's centre line).
        centre_z = 0.5
        for k, (ia, ib, ic) in enumerate(f):
            a, b, c = v[ia], v[ib], v[ic]
            normal = np.cross(b - a, c - a)
            centroid = (a + b + c) / 3
            cap = cap_dir.get(tuple(np.round(centroid, 4)))
            if not cap:
                continue                          # loft faces are wound outwards already
            outward = np.array([cap, 0.0, 0.0])   # the end caps face forwards / backwards
            if np.dot(normal, outward) < 0:
                f[k] = (ia, ic, ib)
        faces_out = [f]
        verts = [v]
        inner_keys = {tuple(np.round(np.mean(np.asarray(t), axis=0), 4)) for t in inner_tris.get(material, [])}
        inner_f = np.asarray([face for face in f
                              if tuple(np.round(v[face].mean(axis=0), 4)) in inner_keys], dtype=int).reshape(-1, 3)
        if len(inner_f):
            # Inner shell of the cabin (pillars, roof): reversed faces 4 mm inside, seen from the seats.
            inner_v = v.copy()
            for k, (ia, ib, ic) in enumerate(inner_f):
                a, b, c = v[ia], v[ib], v[ic]
                normal = np.cross(b - a, c - a)
                length = np.linalg.norm(normal)
                if length > 1e-12:
                    offset = normal / length * 0.004
                    inner_v[ia] = a - offset
                    inner_v[ib] = b - offset
                    inner_v[ic] = c - offset
            faces_out.append(inner_f[:, ::-1] + len(v))
            verts.append(inner_v)
        v_all = np.vstack(verts)
        f_all = np.vstack(faces_out)
        # Drop degenerate faces (the collapsed greenhouse outside the cabin).
        keep = []
        for ia, ib, ic in f_all:
            area = np.linalg.norm(np.cross(v_all[ib] - v_all[ia], v_all[ic] - v_all[ia]))
            if area > 1e-9:
                keep.append((ia, ib, ic))
        import trimesh
        mesh = trimesh.Trimesh(vertices=v_all, faces=np.asarray(keep), process=True)
        path = out_dir / f"body_{material}.obj"
        path.write_text(f"# Hakoniwa Car 2 body, material {material} (generated by config/body_mesh.py)\n"
                        + trimesh.exchange.obj.export_obj(mesh, include_normals=True, include_texture=False,
                                                          header=None), encoding="utf-8")
        written[material] = path
    return written


if __name__ == "__main__":
    for material, path in build(Path(__file__).resolve().parent / "meshes").items():
        print(material, path)
