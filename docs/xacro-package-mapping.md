# ROS-free xacro package mapping

`tools/xacro2urdf.py` can expand xacro files that use ROS-style `$(find PACKAGE)` references without requiring a ROS installation.

Provide each required package root explicitly with `--package NAME=PATH`:

```bash
python3 tools/xacro2urdf.py \
  path/to/robot.urdf.xacro \
  -o path/to/robot.urdf \
  --package sr_description=path/to/sr_description \
  --arg hand_version=E3M5 \
  --arg side=right
```

`--package` may be repeated when the xacro tree references multiple packages.

## Behavior

- `$(find NAME)` resolves only from explicit `--package NAME=PATH` mappings.
- Package paths are normalized to absolute local directories before xacro processing.
- An unmapped `$(find NAME)` fails with a message that tells the caller which `--package` mapping is missing.
- When no `--package` option is supplied, the existing early validation remains: ROS-style `$(find ...)` references are rejected before xacro processing.
- `--arg NAME=VALUE` continues to pass xacro arguments independently of package resolution.

This keeps the conversion path ROS-free and deterministic: package discovery is never inferred from a ROS workspace or environment.

## Scope

Package mapping resolves xacro-time `$(find PACKAGE)` expressions only. Generated URDF references such as `package://PACKAGE/meshes/...` are left unchanged. Asset-path rewriting belongs to the downstream URDF consumer or conversion stage.
