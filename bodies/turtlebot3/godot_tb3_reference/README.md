# TurtleBot3 Godot Reference Scene

This is a hand-written reference scene for validating the Hakoniwa Viewer Model output.

Expected Godot project layout:

```text
res://
  TurtleBot3.reference.tscn
  tb3_reference_sync.gd
  parts/
    base_link.glb
    wheel_left_link.glb
    wheel_right_link.glb
    base_scan.glb
```

## Validation points

1. Open `TurtleBot3.reference.tscn` in Godot.
2. Confirm `base_link` appears at the origin.
3. Confirm `wheel_left_link` is mounted at `(0, 0.08, 0.023)`.
4. Confirm `wheel_right_link` is mounted at `(0, -0.08, 0.023)`.
5. Confirm both wheels use `rotation = Vector3(-1.5708, 0, 0)`.
6. Confirm `base_scan` is mounted at `(-0.032, 0, 0.172)`.
7. If this scene looks correct, the generator should emit this same node pattern.

## Design note

Each GLB is placed under a wrapper `Node3D`.

```text
wheel_left_link
  model(instance of wheel_left_link.glb)
```

The wrapper node owns the mount transform and later receives joint rotation.
This is safer than rotating the GLB instance root directly.
