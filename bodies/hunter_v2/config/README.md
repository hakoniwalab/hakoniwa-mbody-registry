# Hunter V2 Ackermann body

This body validates the Ackermann Forge against an external Xacro/DAE model,
not a Hakoniwa-authored MJCF. The upstream source is pinned in
`sources/hunter_v2.yaml` and is materialized locally under `source/`.

```bash
python tools/ackermann/forge.py hunter_v2
python tools/ackermann/forge.py hunter_v2 --verify
python tools/ackermann/validate.py hunter_v2
```

The Forge performs only the adaptations declared in
`ackermann-forge.yaml`: ROS-free package resolution, deterministic mesh paths,
DAE-to-OBJ conversion, and removal of the two mimic couplings that conflict
with independent Ackermann wheel targets. Gazebo and ros2_control runtime
extensions are explicitly removed by Recipe because they are not body geometry
and cannot be loaded by MuJoCo. Physical overlays remain explicit in the
sibling YAML files.

`joint_dynamics.yaml` records one essential porting adaptation: the upstream
wheel effort limit is lower than its own joint friction loss, so an unchanged
conversion cannot move. The declared MuJoCo force/friction values are simulator
port values, not measured Hunter V2 characteristics. The shared headless
validator guards against this class of structurally valid but unusable port.

`visual_materials.yaml` is the reproducible visual presentation source of
truth. The upstream DAE does not provide a portable chassis material, so the
port explicitly assigns a metallic gray body and black tires. These are visual
approximations, not measured Hunter V2 material properties. The blue checker
floor is likewise declared in `mujoco_world.yaml`.

Upstream source and meshes are Apache-2.0 and remain locally materialized. See
`provenance.yaml`; do not describe this model as Hakoniwa-owned geometry.
