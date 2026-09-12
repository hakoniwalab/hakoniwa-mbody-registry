# MuJoCo robot/world composition

`tools/compose_mujoco_world.py` combines an already prepared robot MJCF with an independently generated world MJCF.

Typical use:

```bash
python tools/compose_mujoco_world.py \
  bodies/generic_ackermann_golf_cart/generated/model.minimal_world.xml \
  /path/to/city-world.xml \
  --output /tmp/golf-cart-city.xml
```

To override the composed robot's initial position without changing the source robot model:

```bash
python tools/compose_mujoco_world.py \
  bodies/generic_ackermann_golf_cart/generated/model.minimal_world.xml \
  /path/to/city-world.xml \
  --robot-pos "0 0 8.5" \
  --output /tmp/golf-cart-city.xml
```

`--robot-pos` is an absolute MuJoCo `pos="X Y Z"` override on the robot model's single top-level body. It intentionally fails when the robot model contains zero or multiple top-level bodies so composition does not silently collapse a multi-body scene.

The generated XML is loaded with MuJoCo before the command succeeds. Use `--no-validate` only when the caller intentionally wants artifact generation without MuJoCo validation.

## Composition contract

The robot XML is the base model. This preserves robot-owned runtime sections such as actuators, contacts, sensors, tendons, equality constraints, and controller-facing names.

The world contributes:

- `<size>`: numeric attributes are merged by taking the maximum robot/world value for each attribute
- `<asset>`: assets are appended after file paths are rebased relative to the generated XML
- `<worldbody>`: world children are inserted before the robot worldbody children

A top-level robot worldbody geom named `ground` is removed by default. This makes a generated minimal robot world usable with an environment that already owns terrain or ground collision. Pass `--keep-robot-ground` to preserve it.

The robot remains authoritative for world-global sections that cannot be combined safely without additional policy:

- `<compiler>`
- `<option>`
- `<visual>`
- `<statistic>`

If these sections are present in the world XML, the tool emits a warning and does not import them.

Other world top-level sections are rejected rather than silently discarded. This includes runtime-oriented sections such as world-owned actuators, sensors, tendons, or contacts.

## Safety checks

The composer:

- rejects output paths that overwrite either input XML
- rejects duplicate named objects between the robot asset/worldbody and the world asset/worldbody
- treats `<freejoint>` and `<joint>` names as the same joint-name namespace for collision detection
- checks that referenced asset files exist
- normalizes robot and world asset file paths for the output location
- removes robot `assetdir`, `meshdir`, and `texturedir` compiler prefixes after rebasing asset paths
- requires exactly one top-level robot body when `--robot-pos` is used
- loads the generated model with MuJoCo by default

## Responsibility boundary

This tool is a build-time MBody target exporter. It does not own simulation stepping, controller behavior, PDU transport, time synchronization, or application orchestration.

A downstream workflow such as Hakoniwa Business Pack can select a robot and a world, run this composer, and hand the resulting MJCF to a runtime such as `hakoniwa-mujoco-robots`.
