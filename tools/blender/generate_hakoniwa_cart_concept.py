#!/usr/bin/env python3
"""Generate a low/mid-poly Hakoniwa Cart concept and export it as GLB.

The coordinate system follows the existing generic Ackermann cart:
  X forward, Y left, Z up.

Reference dimensions retained from config/model.xml:
  wheel centers X = +/-0.775 m, Y = +/-0.52 m
  tire radius = 0.25 m
  seat reference X = -0.34 m

Run with:
  blender --background --python tools/blender/generate_hakoniwa_cart_concept.py
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "bodies/generic_ackermann_golf_cart/generated/concepts"
GLB_PATH = OUT_DIR / "hakoniwa_cart_concept.glb"
BLEND_PATH = OUT_DIR / "hakoniwa_cart_concept.blend"
PREVIEW_PATH = OUT_DIR / "hakoniwa_cart_concept_preview.png"


def clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def material(name: str, color, metallic=0.0, roughness=0.4, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color[:3], color[3] if len(color) > 3 else 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = mat.diffuse_color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        emission_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        emission_input.default_value = (*emission[:3], 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    if mat.diffuse_color[3] < 1.0:
        bsdf.inputs["Alpha"].default_value = mat.diffuse_color[3]
        transmission_input = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
        transmission_input.default_value = 0.25
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        else:
            mat.blend_method = "BLEND"
    return mat


WHITE = material("Warm white body", (0.92, 0.91, 0.88, 1.0), 0.05, 0.22)
DARK = material("Lower graphite", (0.055, 0.065, 0.075, 1.0), 0.15, 0.28)
TRIM = material("Dark grey trim", (0.12, 0.135, 0.15, 1.0), 0.1, 0.32)
BLACK = material("Lamp housing black", (0.008, 0.012, 0.018, 1.0), 0.12, 0.18)
RUBBER = material("Tire rubber", (0.018, 0.022, 0.025, 1.0), 0.0, 0.7)
RIM = material("Wheel alloy", (0.23, 0.25, 0.27, 1.0), 0.75, 0.2)
CREAM = material("Seat ivory", (0.72, 0.70, 0.65, 1.0), 0.0, 0.62)
SEAT_DARK = material("Seat side", (0.075, 0.08, 0.085, 1.0), 0.0, 0.55)
ORANGE = material("Hakoniwa orange", (1.0, 0.22, 0.015, 1.0), 0.05, 0.28,
                  emission=(1.0, 0.09, 0.002), strength=3.5)
LED = material("Cool white LED", (0.78, 0.92, 1.0, 1.0), 0.05, 0.12,
               emission=(0.55, 0.8, 1.0), strength=7.0)
GLASS = material("Windshield glass", (0.06, 0.10, 0.13, 0.28), 0.0, 0.12)
LENS = material("Lamp lens", (0.09, 0.13, 0.17, 0.85), 0.25, 0.12)

MODEL_OBJECTS = []


def keep(obj):
    MODEL_OBJECTS.append(obj)
    return obj


def assign(obj, mat):
    if mat:
        obj.data.materials.append(mat)
    return keep(obj)


def box(name, location, scale, mat, bevel=0.04, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (scale[0] / 2, scale[1] / 2, scale[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Soft product edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
    return assign(obj, mat)


def cylinder(name, location, radius, depth, mat, rotation=(0, 0, 0), vertices=24, bevel=0.0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                       location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    if bevel:
        mod = obj.modifiers.new("Edge bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return assign(obj, mat)


def torus(name, location, major, minor, mat, rotation=(0, 0, 0), major_segments=24, minor_segments=8):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                    major_segments=major_segments, minor_segments=minor_segments,
                                    location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return assign(obj, mat)


def tube(name, points, radius, mat, cyclic=False, resolution=1):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, co in zip(spline.bezier_points, points):
        bp.co = co
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return assign(obj, mat)


def quad_panel(name, verts, mat, solidify=0.015, bevel=0.018):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    sol = obj.modifiers.new("Panel thickness", "SOLIDIFY")
    sol.thickness = solidify
    if bevel:
        bev = obj.modifiers.new("Panel edge", "BEVEL")
        bev.width = bevel
        bev.segments = 2
    return assign(obj, mat)


def wheel(x, y, name):
    # Existing model: wheel center x=+/-0.775, y=+/-0.52, radius=0.25.
    center = (x, y, 0.25)
    cylinder(f"{name}_tire", center, 0.25, 0.18, RUBBER,
             rotation=(math.radians(90), 0, 0), vertices=32, bevel=0.015)
    cylinder(f"{name}_rim", center, 0.155, 0.188, RIM,
             rotation=(math.radians(90), 0, 0), vertices=20, bevel=0.01)
    cylinder(f"{name}_hub", (x, y + (0.101 if y > 0 else -0.101), 0.25), 0.055, 0.018,
             DARK, rotation=(math.radians(90), 0, 0), vertices=20, bevel=0.008)
    # Five low-poly spokes on the visible outer face.
    outer_y = y + (0.102 if y > 0 else -0.102)
    for i in range(5):
        angle = math.radians(i * 72)
        sx = x + math.cos(angle) * 0.09
        sz = 0.25 + math.sin(angle) * 0.09
        spoke = box(f"{name}_spoke_{i}", (sx, outer_y, sz), (0.13, 0.018, 0.032), DARK,
                    bevel=0.008, rotation=(0, -angle, 0))
        spoke.rotation_euler.y = -angle


def headlamp(y, side):
    # Axis is X, so the rings face forward.
    x = 0.956
    z = 0.825
    box(f"{side}_lamp_housing", (0.925, y, z), (0.09, 0.245, 0.225), BLACK, bevel=0.055)
    torus(f"{side}_daylight_ring", (x, y, z), 0.077, 0.012, LED,
          rotation=(0, math.radians(90), 0), major_segments=28, minor_segments=8)
    cylinder(f"{side}_lens", (x + 0.006, y, z), 0.058, 0.025, LENS,
             rotation=(0, math.radians(90), 0), vertices=24, bevel=0.006)
    cylinder(f"{side}_projector", (x + 0.022, y, z), 0.026, 0.012, BLACK,
             rotation=(0, math.radians(90), 0), vertices=20)


def seat(y, side):
    # Split the existing bench around its source position x=-0.34.
    box(f"{side}_seat_base_side", (-0.34, y, 0.91), (0.48, 0.39, 0.16), SEAT_DARK, 0.055)
    box(f"{side}_seat_cushion", (-0.31, y, 0.965), (0.45, 0.35, 0.13), CREAM, 0.06)
    box(f"{side}_seat_back_side", (-0.53, y, 1.24), (0.15, 0.39, 0.56), SEAT_DARK, 0.06,
        rotation=(0, math.radians(-5), 0))
    box(f"{side}_seat_back", (-0.505, y, 1.25), (0.12, 0.35, 0.50), CREAM, 0.055,
        rotation=(0, math.radians(-5), 0))
    tube(f"{side}_seat_accent", [(-0.29, y, 1.02), (-0.48, y, 1.47)], 0.007, ORANGE)


def create_model():
    # Wheels and low chassis.
    for x, axle in ((0.775, "front"), (-0.775, "rear")):
        for y, side in ((0.52, "left"), (-0.52, "right")):
            wheel(x, y, f"{axle}_{side}")

    box("chassis", (-0.02, 0, 0.43), (1.74, 0.91, 0.18), DARK, 0.045)
    box("floor_step", (-0.28, 0, 0.56), (0.90, 0.90, 0.12), TRIM, 0.035)
    box("front_undertray", (0.60, 0, 0.51), (0.54, 0.92, 0.20), TRIM, 0.055)
    box("rear_body", (-0.68, 0, 0.71), (0.42, 0.92, 0.50), WHITE, 0.075)

    # The priority feature: one-piece white face with black lamp band and bumper.
    box("front_white_face", (0.74, 0, 0.77), (0.38, 0.91, 0.52), WHITE, 0.085)
    box("front_black_lamp_bridge", (0.944, 0, 0.825), (0.055, 0.82, 0.105), BLACK, 0.035)
    box("front_led_bar", (0.977, 0, 0.825), (0.018, 0.455, 0.026), LED, 0.010)
    headlamp(0.325, "left")
    headlamp(-0.325, "right")

    # Lower bumper with a separate center skid volume.
    box("lower_bumper", (0.92, 0, 0.49), (0.24, 1.00, 0.25), DARK, 0.06)
    box("lower_skid", (1.035, 0, 0.43), (0.11, 0.61, 0.12), TRIM, 0.035)
    for y, side in ((0.455, "left"), (-0.455, "right")):
        box(f"{side}_amber_marker", (1.035, y, 0.55), (0.018, 0.026, 0.13), ORANGE, 0.012)

    # Fender shoulders visually carry the front face into the side sills.
    for y, side in ((0.48, "left"), (-0.48, "right")):
        tube(f"{side}_front_fender",
             [(0.47, y, 0.40), (0.53, y, 0.62), (0.73, y, 0.76),
              (0.93, y, 0.64), (1.00, y, 0.44)], 0.065, TRIM)
        box(f"{side}_white_shoulder", (0.61, y * 0.91, 0.73), (0.52, 0.08, 0.33), WHITE, 0.045,
            rotation=(0, math.radians(-8), 0))
        box(f"{side}_sill", (-0.20, y * 0.92, 0.48), (1.03, 0.09, 0.18), DARK, 0.03)

    # Windshield and frame. Front posts sweep rearwards toward the roof.
    tube("front_left_post", [(0.61, 0.46, 0.88), (0.46, 0.46, 1.91)], 0.035, DARK)
    tube("front_right_post", [(0.61, -0.46, 0.88), (0.46, -0.46, 1.91)], 0.035, DARK)
    tube("rear_left_post", [(-0.78, 0.46, 0.78), (-0.78, 0.46, 1.91)], 0.035, DARK)
    tube("rear_right_post", [(-0.78, -0.46, 0.78), (-0.78, -0.46, 1.91)], 0.035, DARK)
    quad_panel("windshield",
               [(0.602, -0.43, 0.91), (0.602, 0.43, 0.91),
                (0.458, 0.43, 1.87), (0.458, -0.43, 1.87)], GLASS, 0.012, 0.012)
    box("dashboard", (0.39, 0, 0.88), (0.43, 0.81, 0.14), DARK, 0.055,
        rotation=(0, math.radians(-7), 0))

    # Roof uses the original 1.8 x 1.06 m footprint.
    box("roof_dark_underlay", (-0.08, 0, 1.94), (1.82, 1.08, 0.08), DARK, 0.055)
    box("roof_white_shell", (-0.08, 0, 1.985), (1.90, 1.13, 0.09), WHITE, 0.065)
    for y, side in ((0.545, "left"), (-0.545, "right")):
        box(f"roof_{side}_orange_line", (-0.08, y, 1.988), (1.52, 0.012, 0.022), ORANGE, 0.006)

    # Existing seat reference becomes two individual occupant positions.
    seat(0.225, "left")
    seat(-0.225, "right")

    # Steering wheel and column on the right-hand side.
    tube("steering_column", [(0.25, -0.23, 0.98), (0.18, -0.23, 1.18)], 0.045, DARK)
    torus("steering_wheel", (0.15, -0.23, 1.23), 0.145, 0.022, BLACK,
          rotation=(0, math.radians(67), 0), major_segments=24, minor_segments=8)

    # Side safety rails and mirrors.
    for y, side, sign in ((0.47, "left", 1), (-0.47, "right", -1)):
        tube(f"{side}_seat_rail",
             [(-0.63, y, 0.93), (-0.43, y, 1.05), (-0.12, y, 1.05)], 0.025, DARK)
        tube(f"{side}_mirror_arm", [(0.48, y, 1.48), (0.60, y + sign * 0.09, 1.51)], 0.018, DARK)
        box(f"{side}_mirror", (0.61, y + sign * 0.12, 1.53), (0.09, 0.07, 0.20), DARK, 0.03)
        box(f"{side}_mirror_signal", (0.655, y + sign * 0.12, 1.53), (0.012, 0.012, 0.105), ORANGE, 0.005)

    # Rear graphic volumes complete the prototype from all angles.
    box("rear_white_face", (-0.90, 0, 0.77), (0.16, 0.90, 0.43), WHITE, 0.06)
    box("rear_black_lamp_bridge", (-0.987, 0, 0.80), (0.026, 0.76, 0.09), BLACK, 0.025)
    for y, side in ((0.33, "left"), (-0.33, "right")):
        torus(f"rear_{side}_lamp", (-1.006, y, 0.80), 0.064, 0.012, ORANGE,
              rotation=(0, math.radians(90), 0), major_segments=24, minor_segments=8)

    # Front wordmark, kept as geometry for GLB portability.
    bpy.ops.object.text_add(location=(0.974, 0, 0.995), rotation=(math.radians(90), 0, math.radians(90)))
    text = bpy.context.object
    text.name = "HAKONIWA_wordmark"
    text.data.body = "HAKONIWA"
    text.data.align_x = "CENTER"
    text.data.align_y = "CENTER"
    text.data.size = 0.075
    text.data.extrude = 0.002
    text.data.space_character = 1.15
    text.data.materials.append(TRIM)
    keep(text)


def export_model():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in MODEL_OBJECTS:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = MODEL_OBJECTS[0]
    bpy.ops.export_scene.gltf(
        filepath=str(GLB_PATH),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
    )


def setup_preview():
    # Neutral studio ground and backdrop for a front three-quarter QA render.
    ground_mat = material("Preview ground", (0.16, 0.17, 0.18, 1.0), 0.0, 0.72)
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -0.01))
    ground = bpy.context.object
    ground.name = "Preview ground (not exported)"
    ground.data.materials.append(ground_mat)

    world = bpy.context.scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.045, 0.055, 0.07, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

    for name, loc, energy, size, color in (
        ("Key", (4.2, -4.0, 5.2), 1250, 4.0, (1.0, 0.88, 0.78)),
        ("Fill", (2.0, 4.2, 3.5), 900, 3.5, (0.65, 0.78, 1.0)),
        ("Rim", (-3.5, 1.5, 4.0), 1050, 3.0, (0.8, 0.9, 1.0)),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = color
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = loc
        point_camera(obj, Vector((0, 0, 0.95)))

    bpy.ops.object.camera_add(location=(4.2, -4.0, 2.65))
    cam = bpy.context.object
    cam.name = "Preview camera"
    point_camera(cam, Vector((0.0, 0.0, 0.95)))
    cam.data.lens = 58
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if bpy.app.version >= (4, 2, 0) else "BLENDER_EEVEE"
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW_PATH)
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast" if bpy.app.version >= (4, 0, 0) else "Medium High Contrast"
    scene.render.resolution_percentage = 100
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.ops.render.render(write_still=True)


def point_camera(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def main():
    clean_scene()
    create_model()
    export_model()
    setup_preview()
    print(f"GLB: {GLB_PATH}")
    print(f"BLEND: {BLEND_PATH}")
    print(f"PREVIEW: {PREVIEW_PATH}")


if __name__ == "__main__":
    main()
