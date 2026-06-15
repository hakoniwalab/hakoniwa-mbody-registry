# Hakoniwa View Model

## Purpose

The Hakoniwa view-model is a small, generated manifest for reconstructing a robot body for visualization and view-side synchronization.

It exists because Hakoniwa integrates multiple runtimes horizontally. Each runtime should not have to understand the full source robot description format, nor should each runtime re-implement the same MJCF body and joint traversal logic.

The view-model is therefore a thin contract between generated robot body assets and downstream viewers or runtime adapters.

```text
xacro / urdf -> mjcf
mjcf -> parts.glb
mjcf -> view-model
```

## Canonical model relationship

The view-model is not a new robot description language.

Hakoniwa mbody treats MJCF as the canonical normalized body model. The view-model is derived from MJCF and should be reproducible from MJCF plus a small recipe.

```text
MJCF       = canonical normalized body model
parts.glb  = visual body assets generated from MJCF / URDF
view-model = view-only manifest that maps body / joint semantics to visual assets
```

The authority remains in the MJCF. The view-model is an index optimized for consumers that need to assemble, display, or synchronize the visual body.

The human-authored input used to generate this file is documented separately in [view-model-recipe.md](view-model-recipe.md).

## Scope

The view-model may describe:

- robot name
- root / base body
- coordinate system metadata
- visual asset list
- body name
- parent body name
- asset reference
- mount transform
- fixed parts
- movable parts
- joint name
- view-side motion type
- view-side motion axis

The view-model must not describe:

- PDU channels
- endpoint configuration
- shared-memory paths
- actuator configuration
- sensor runtime configuration
- controller behavior
- Godot `NodePath`
- Godot scene files such as `.tscn`
- GDScript wrappers
- MuJoCo solver parameters
- physics execution behavior

In short, the view-model is view-only. It does not define control, communication, or runtime execution.

## File placement

Recommended generated layout:

```text
bodies/<robot>/generated/
  <model>.xml
  parts/
    <body>.glb
  view-model.json
```

The `parts/*.glb` files are visual assets. The `view-model.json` file describes how those visual assets correspond to MJCF bodies and joints.

## Top-level structure

A view-model JSON document has the following top-level fields.

| Field | Required | Description |
|---|---:|---|
| `format` | yes | Format identifier. Current value: `hako_viewer_model` |
| `version` | yes | View-model schema version, for example `0.1` |
| `coordinate_system` | yes | Coordinate system used by the generated values, for example `ros` |
| `robot` | yes | Robot metadata |
| `assets` | yes | Visual asset list |
| `base` | yes | Root visual part |
| `movable_parts` | no | Parts driven by joints |
| `fixed_parts` | no | Additional fixed parts under the visual tree |

## Robot metadata

```json
{
  "robot": {
    "name": "turtlebot3_burger",
    "root": "base_link"
  }
}
```

`robot.root` is the base body used by the view-model. Consumers may use it as the visual root or as the anchor for a runtime-specific scene graph.

## Assets

Each asset entry declares a generated visual asset.

```json
{
  "id": "wheel_left_link",
  "type": "glb",
  "path": "parts/wheel_left_link.glb"
}
```

`id` is referenced by `base`, `fixed_parts`, and `movable_parts`.

For now, `type` is limited to `glb`.

## Parts

A part maps an MJCF body to a visual asset.

```json
{
  "name": "base_scan",
  "parent": "base_link",
  "asset": "base_scan",
  "mount": {
    "xyz": [-0.032, 0.0, 0.172],
    "rpy": [0.0, 0.0, 0.0]
  }
}
```

`mount` is the local transform from the parent body to this part. `xyz` is translation and `rpy` is roll, pitch, yaw in radians.

The base part uses an identity mount by convention.

## Movable parts

A movable part extends a part with joint and motion metadata.

```json
{
  "name": "wheel_left_link",
  "joint": "wheel_left_joint",
  "parent": "base_link",
  "asset": "wheel_left_link",
  "mount": {
    "xyz": [0.0, 0.08, 0.023],
    "rpy": [-1.569999, 0.0, 0.0]
  },
  "motion": {
    "type": "continuous",
    "axis": [0.0, 0.0, 1.0]
  }
}
```

`joint` is the MJCF joint name. `motion` describes how the part may move for view-side reconstruction and synchronization.

## Motion model

The motion model is intentionally limited to view-side semantics derived from MJCF joint types.

| MJCF joint type | View-model `motion.type` | Notes |
|---|---|---|
| `hinge` | `continuous` or `revolute` | `continuous` is acceptable when limit/range semantics are not needed by the viewer |
| `slide` | `prismatic` | Linear motion |
| `free` | `free` | Optional; use only when a view consumer needs it |
| `ball` | `ball` | Optional; use only when a view consumer needs it |

For `continuous`, `revolute`, and `prismatic`, `axis` is required.

The motion model is not an actuator model. It does not define control range, motor gear, controller behavior, or physics behavior.

## Example

```json
{
  "format": "hako_viewer_model",
  "version": "0.1",
  "coordinate_system": "ros",
  "robot": {
    "name": "turtlebot3_burger",
    "root": "base_link"
  },
  "assets": [
    {
      "id": "base_link",
      "type": "glb",
      "path": "parts/base_link.glb"
    },
    {
      "id": "wheel_left_link",
      "type": "glb",
      "path": "parts/wheel_left_link.glb"
    }
  ],
  "base": {
    "name": "base_link",
    "asset": "base_link",
    "mount": {
      "xyz": [0.0, 0.0, 0.0],
      "rpy": [0.0, 0.0, 0.0]
    }
  },
  "movable_parts": [
    {
      "name": "wheel_left_link",
      "joint": "wheel_left_joint",
      "parent": "base_link",
      "asset": "wheel_left_link",
      "mount": {
        "xyz": [0.0, 0.08, 0.023],
        "rpy": [-1.569999, 0.0, 0.0]
      },
      "motion": {
        "type": "continuous",
        "axis": [0.0, 0.0, 1.0]
      }
    }
  ]
}
```

## Schema

The JSON Schema lives at:

```text
schemas/view-model.schema.json
```

Generated view-model files should validate against this schema.

Example validation with Python `jsonschema`:

```bash
python3 -m pip install jsonschema
python3 - <<'PY'
import json
from pathlib import Path
from jsonschema import validate

schema = json.loads(Path("schemas/view-model.schema.json").read_text())
model = json.loads(Path("bodies/turtlebot3/view/turtlebot3.json").read_text())
validate(instance=model, schema=schema)
print("view-model schema validation OK")
PY
```

## Versioning policy

The view-model should remain small and mostly append-only.

- Additive fields may be introduced in a new minor version.
- Breaking changes require a version bump.
- Runtime-specific fields should not be added to this schema.
- If a downstream runtime needs extra data, it should keep that data in its own runtime-specific profile or overlay.

## Design rule

```text
view-model is view only.
motion is derived from MJCF joint semantics.
control, communication, and runtime execution stay outside the view-model.
```
