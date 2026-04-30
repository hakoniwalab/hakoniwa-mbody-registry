# hakoniwa-mbody-registry

Robot body definitions as molds — convert to URDF, MJCF, and GLB for Hakoniwa simulations.

## What is this?

This repository helps you take an existing robot description and turn it into simulation-ready assets you can actually use.

It is for people who need robot geometry in practical formats:

- robotics researchers who want a reproducible model registry
- simulation developers who need URDF or MuJoCo XML
- game engine or 3D tool users who want GLB assets
- ML / RL engineers who want robot bodies without adopting a full ROS stack

The main value is simple: fetch once, convert once, and keep the generated assets under a predictable local layout.

The ROS-free part matters because it lowers setup cost. You can work with robot body assets using standard Python tools, without installing or maintaining a full ROS environment.

## Registry Pattern

This repository follows the same registry idea as `hakoniwa-pdu-registry`.

- `sources/` stores where the robot description came from
- `tools/` stores how to convert it
- `bodies/{name}/generated/` stores the committed outputs that downstream users can consume directly

Committing generated artifacts is intentional here. It means users can use URDF, MuJoCo XML, and GLB outputs without running the whole conversion pipeline themselves, and upstream robot changes show up as versioned diffs.

## Overview

`hakoniwa-mbody-registry` is a **ROS-independent** registry of robot physical body definitions (mold-bodies) for the [Hakoniwa](https://github.com/hakoniwalab) simulation ecosystem.

It is the physical counterpart to [`hakoniwa-pdu-registry`](https://github.com/hakoniwalab/hakoniwa-pdu-registry):

| Repository | Role |
|---|---|
| `hakoniwa-pdu-registry` | Data communication type definitions (ROS IDL-based) |
| `hakoniwa-mbody-registry` | Robot physical body definitions (xacro-based) |

Each robot body is defined as a **mold** (mbody) — a xacro-based source definition that can be cast into multiple simulation formats.

## Toolchain

```text
fetch.py
  -> upstream robot description
  -> local source snapshot under bodies/{name}/source/

xacro2urdf.py
  -> xacro / xacro-enabled URDF
  -> bodies/{name}/generated/{model}.urdf

urdf2mjcf.py
  -> plain URDF
  -> bodies/{name}/generated/{model}.xml

urdf2glb.py
  -> plain URDF
  -> bodies/{name}/generated/{model}.glb

mjcf2glb.py
  -> canonical MuJoCo XML
  -> bodies/{name}/generated/parts/*.glb

mjcf_add_actuators.py
  -> canonical MuJoCo XML + actuator YAML
  -> actuated MuJoCo XML

mjcf2pdu.py
  -> canonical MuJoCo XML + body-to-PDU YAML
  -> Hakoniwa pdutypes.json
```

All tools are bundled in `tools/` and are intended to work without a ROS installation.

## Dependencies

The tools require these Python packages:

```bash
python3 -m pip install -r requirements.txt
```

## Repository Structure

```
hakoniwa-mbody-registry/
├── requirements.txt      # Python dependencies for the toolchain
├── tools/
│   ├── fetch.py          # Sparse fetch from upstream Git repositories
│   ├── xacro2urdf.py     # ROS-free xacro / xacro-enabled URDF -> plain URDF
│   ├── urdf2mjcf.py      # URDF -> canonical MuJoCo XML
│   ├── urdf2glb.py       # URDF -> single GLB scene
│   ├── mjcf2glb.py       # MuJoCo XML -> split GLB assets
│   ├── mjcf_add_actuators.py # Actuator YAML -> actuated MuJoCo XML
│   ├── mjcf2pdu.py       # MJCF body list -> Hakoniwa pdutypes.json
│   └── forge.sh          # Full pipeline wrapper
├── bodies/               # Registry-managed source snapshots and generated artifacts
│   └── turtlebot3/
│       ├── config/       # Robot-specific actuator or postprocess settings, committed
│       ├── source/       # Fetched upstream files, not committed
│       └── generated/    # Converted artifacts, committed
├── docs/
│   └── images/           # Placeholder location for README screenshots
├── sources/              # Declarative fetch definitions per robot
│   └── tb3.yaml          # TurtleBot3
└── README.md
```

### `sources/` — Fetch Definitions

Each YAML file declares where to fetch robot source files from and which paths to retrieve:

```yaml
name: turtlebot3
repo: https://github.com/ROBOTIS-GIT/turtlebot3
branch: humble
files:
  - turtlebot3_description/
```

Running `tools/fetch.py` reads these files and performs a sparse checkout of only the listed paths into `bodies/{name}/source/`, preserving the upstream relative paths.

### `bodies/` layout

- `bodies/{name}/source/`
  Fetched from upstream. This is a local snapshot used as conversion input and is not committed.
- `bodies/{name}/generated/`
  Generated artifacts. These are committed as registry outputs for downstream users.
- `bodies/{name}/config/`
  Robot-specific settings such as actuator mappings and body-to-PDU mappings that are not present in standard URDF.

## Tools

### `tools/fetch.py`

Fetch only the robot files you need from an upstream Git repository.

- Input: `sources/*.yaml`
- Output: `bodies/{name}/source/...`

### `tools/xacro2urdf.py`

Turn a xacro-based robot description into a plain URDF file.

- Input: `.xacro` or xacro-enabled `.urdf`
- Output: `bodies/{name}/generated/{stem}.urdf` by default when the input is under `bodies/{name}/`
- Supports `--arg NAME=VALUE`
- Detects unsupported ROS-style `$(find ...)` expressions and fails early with file and line information

Example:

```bash
python3 tools/xacro2urdf.py \
  bodies/turtlebot3/source/turtlebot3_description/urdf/turtlebot3_burger.urdf
```

### `tools/urdf2mjcf.py`

Convert a plain URDF into canonical MuJoCo XML using MuJoCo's official compiler.

- Input: plain URDF
- Output: `bodies/{name}/generated/{stem}.xml` by default when the input is under `bodies/{name}/`
- Rewrites `package://...` mesh references before invoking MuJoCo
- If the package root cannot be inferred from the input path, pass `--package-root PACKAGE=PATH`

Example:

```bash
python3 tools/urdf2mjcf.py \
  bodies/turtlebot3/generated/turtlebot3_burger.urdf
```

### `tools/urdf2glb.py`

Export the robot's visual geometry as one GLB scene.

- Input: plain URDF
- Output: `bodies/{name}/generated/{stem}.glb` by default when the input is under `bodies/{name}/`
- Supports mesh, box, cylinder, and sphere visuals
- Supports `package://...` mesh references

Example:

```bash
python3 tools/urdf2glb.py \
  bodies/turtlebot3/generated/turtlebot3_burger.urdf
```

### `tools/mjcf2glb.py`

Split a MuJoCo XML model into smaller GLB assets that match its body or geom structure.

- Input: canonical MuJoCo XML produced by `urdf2mjcf.py`
- Output: `bodies/{name}/generated/parts/*.glb` by default when the input is under `bodies/{name}/`
- Default: `--split-by body`
- Alternative: `--split-by geom`

Example:

```bash
python3 tools/mjcf2glb.py \
  bodies/turtlebot3/generated/turtlebot3_burger.xml
```

### `tools/mjcf_add_actuators.py`

Add control definitions to a structural MuJoCo XML model using a YAML mapping file.

- Input: canonical MuJoCo XML and an actuator YAML file
- Output: `bodies/{name}/generated/{stem}.actuated.xml` by default when the input is under `bodies/{name}/`
- Validates that referenced joints exist before writing output

Example:

```bash
python3 tools/mjcf_add_actuators.py \
  bodies/turtlebot3/generated/turtlebot3_burger.xml \
  bodies/turtlebot3/config/actuators.yaml
```

Example YAML:

```yaml
actuators:
  - type: motor
    name: left_motor
    joint: wheel_left_joint
    ctrllimited: true
    ctrlrange: [-10, 10]
    gear: 1.0

  - type: motor
    name: right_motor
    joint: wheel_right_joint
    ctrllimited: true
    ctrlrange: [-10, 10]
    gear: 1.0
```

### `tools/mjcf2pdu.py`

Generate Hakoniwa `pdutypes.json` from a selected list of MJCF bodies.

- Input: canonical MuJoCo XML and a PDU YAML file
- Output: `bodies/{name}/generated/pdutypes.json` by default when the input is under `bodies/{name}/`
- Auto-assigns `channel_id` values starting from `base_channel_id`
- Validates that referenced body names exist in the MJCF

Example:

```bash
python3 tools/mjcf2pdu.py \
  bodies/turtlebot3/generated/turtlebot3_burger.xml \
  bodies/turtlebot3/config/pdu_bodies.yaml
```

Example YAML:

```yaml
base_channel_id: 0
default_pdu_size: 72
default_type: geometry_msgs/Twist
default_name_suffix: pos

bodies:
  - base_link
  - base_scan
  - wheel_left_link
  - wheel_right_link
  - caster_back_link
```

### `tools/pdu_manifest2types.py`

Generate canonical Hakoniwa `pdutypes.json` from `pdu-manifest.yaml`.

- Input: `bodies/{name}/config/pdu-manifest.yaml`
- Output: `bodies/{name}/generated/pdutypes.json` by default
- Flattens `bodies`, `sensors`, and `extras`
- Preserves explicit `channel_id`
- Resolves `pdu_size` from the manifest first, then from the `hakoniwa_pdu` size registry when available

Example:

```bash
python3 tools/pdu_manifest2types.py \
  bodies/turtlebot3/config/pdu-manifest.yaml
```

### `tools/pdu_manifest2def.py`

Generate compact Hakoniwa `pdu_def.json` from `pdu-manifest.yaml`.

- Input: `bodies/{name}/config/pdu-manifest.yaml`
- Output: `bodies/{name}/generated/pdu_def.json` by default
- Emits the compact `paths + robots` form
- Supports overriding `pdutypes_path` and `pdutypes_id`

Example:

```bash
python3 tools/pdu_manifest2def.py \
  bodies/turtlebot3/config/pdu-manifest.yaml \
  --pdutypes-path tb3-pdutypes.json \
  --pdutypes-id tb3-endpoint
```

### `tools/godot_sync2endpoint.py`

Generate Godot `endpoint_shm_with_pdu.json` from `godot_sync.yaml`.

- Input: `bodies/{name}/config/godot_sync.yaml`
- Output: `bodies/{name}/generated/endpoint_shm_with_pdu.json` by default
- Uses `endpoint.endpoint_name`
- Rewrites `endpoint.comm_path` relative to the output location
- Defaults `pdu_def_path` to a sibling `pdu_def.json`

Example:

```bash
python3 tools/godot_sync2endpoint.py \
  bodies/turtlebot3/config/godot_sync.yaml
```

### `tools/godot_sync2profile.py`

Generate Godot `robot_sync.profile.json` from `godot_sync.yaml` and a viewer model JSON.

- Input:
  - `bodies/{name}/config/godot_sync.yaml`
  - viewer model JSON generated by `tools/hako_viewer_model_gen.py`
- Output: `bodies/{name}/generated/godot/robot_sync.profile.json` by default
- Resolves `base_node_path` and `joint_mappings[].node_path` using the same body-name rules as the Godot scene generator

Example:

```bash
python3 tools/hako_viewer_model_gen.py \
  bodies/turtlebot3/config/viewer.recipe.yaml \
  -o /tmp/tb3-viewer.json \
  --pretty

python3 tools/godot_sync2profile.py \
  bodies/turtlebot3/config/godot_sync.yaml \
  /tmp/tb3-viewer.json
```

### `tools/forge.sh`

Run the whole robot conversion flow in one command when you already know the entry URDF path.

- Input: `sources/*.yaml` and an entry URDF path relative to `source/`
- Output: `bodies/{name}/generated/`
- If `bodies/{name}/config/actuators.yaml` exists, also generates an actuated MuJoCo XML file

Example:

```bash
./tools/forge.sh sources/tb3.yaml turtlebot3_description/urdf/turtlebot3_burger.urdf
```

## Quick Start

```bash
# 1. Install dependencies
python3 -m pip install -r requirements.txt

# 2. Run the full TurtleBot3 Burger pipeline
./tools/forge.sh sources/tb3.yaml turtlebot3_description/urdf/turtlebot3_burger.urdf
```

Typical outputs are created under `bodies/turtlebot3/generated/`:

- `turtlebot3_burger.urdf`
- `turtlebot3_burger.xml`
- `turtlebot3_burger.actuated.xml`
- `turtlebot3_burger.glb`
- `pdutypes.json`
- `parts/*.glb`

## Walkthrough: TurtleBot3 Burger

This is the simplest end-to-end example in the repository. It starts from the upstream TurtleBot3 description and produces:

- a plain URDF
- a canonical MuJoCo XML file
- a single GLB scene
- split GLB assets based on the MuJoCo body structure

```bash
# Step 1: Fetch TB3 description from upstream
python3 tools/fetch.py sources/tb3.yaml

# Step 2: Expand xacro to plain URDF
python3 tools/xacro2urdf.py \
  bodies/turtlebot3/source/turtlebot3_description/urdf/turtlebot3_burger.urdf

# Step 3: Convert URDF to MuJoCo XML
python3 tools/urdf2mjcf.py \
  bodies/turtlebot3/generated/turtlebot3_burger.urdf

# Step 4: Convert URDF to GLB (single scene)
python3 tools/urdf2glb.py \
  bodies/turtlebot3/generated/turtlebot3_burger.urdf

# Step 5: Add actuators from YAML
python3 tools/mjcf_add_actuators.py \
  bodies/turtlebot3/generated/turtlebot3_burger.xml \
  bodies/turtlebot3/config/actuators.yaml

# Step 6: Generate Hakoniwa body-state PDU definitions
python3 tools/mjcf2pdu.py \
  bodies/turtlebot3/generated/turtlebot3_burger.xml \
  bodies/turtlebot3/config/pdu_bodies.yaml

# Step 7: Split MuJoCo XML into per-body GLB assets
python3 tools/mjcf2glb.py \
  bodies/turtlebot3/generated/turtlebot3_burger.xml
```

Expected output files:

- `bodies/turtlebot3/generated/turtlebot3_burger.urdf`
- `bodies/turtlebot3/generated/turtlebot3_burger.xml`
- `bodies/turtlebot3/generated/turtlebot3_burger.actuated.xml`
- `bodies/turtlebot3/generated/turtlebot3_burger.glb`
- `bodies/turtlebot3/generated/pdutypes.json`
- `bodies/turtlebot3/generated/parts/*.glb`

## Godot Export

To build a Godot scene from the generated TurtleBot3 assets, first generate the viewer model JSON and then generate the `.tscn` scene.

```bash
# Generate the viewer model JSON from recipe + actuated MJCF
python3 tools/hako_viewer_model_gen.py \
  bodies/turtlebot3/config/viewer.recipe.yaml \
  -o bodies/turtlebot3/view/turtlebot3.json \
  --pretty

# Generate the Godot scene
python3 tools/hako_godot_scene_gen.py \
  bodies/turtlebot3/view/turtlebot3.json \
  -o bodies/turtlebot3/godot_tb3_reference/TurtleBot3.generated.tscn \
  --res-root res:// \
  --sync-script tb3_reference_sync.gd
```

When `--sync-script` is specified, the generator also writes a placeholder GDScript file with the same basename next to the output `.tscn`.

The generated scene expects the split GLB assets under `res://parts/`.

One practical way to stage everything into a Godot project is:

```bash
export GODOT_PROJECT_DIR=/path/to/your/godot/project

mkdir -p "$GODOT_PROJECT_DIR/parts"
cp -f bodies/turtlebot3/generated/parts/*.glb "$GODOT_PROJECT_DIR/parts/"
cp -f bodies/turtlebot3/godot_tb3_reference/TurtleBot3.generated.tscn "$GODOT_PROJECT_DIR/"
cp -f bodies/turtlebot3/godot_tb3_reference/tb3_reference_sync.gd "$GODOT_PROJECT_DIR/"
```

If you want to regenerate and stage in one flow:

```bash
python3 tools/urdf2glb.py \
  bodies/turtlebot3/generated/turtlebot3_burger.urdf \
  --parts-dir bodies/turtlebot3/generated/parts

python3 tools/hako_viewer_model_gen.py \
  bodies/turtlebot3/config/viewer.recipe.yaml \
  -o bodies/turtlebot3/view/turtlebot3.json \
  --pretty

python3 tools/hako_godot_scene_gen.py \
  bodies/turtlebot3/view/turtlebot3.json \
  -o bodies/turtlebot3/godot_tb3_reference/TurtleBot3.generated.tscn \
  --res-root res:// \
  --sync-script tb3_reference_sync.gd

mkdir -p "$GODOT_PROJECT_DIR/parts"
cp -f bodies/turtlebot3/generated/parts/*.glb "$GODOT_PROJECT_DIR/parts/"
cp -f bodies/turtlebot3/godot_tb3_reference/TurtleBot3.generated.tscn "$GODOT_PROJECT_DIR/"
cp -f bodies/turtlebot3/godot_tb3_reference/tb3_reference_sync.gd "$GODOT_PROJECT_DIR/"
```

The resulting Godot node structure is:

```text
TurtleBot3
  HakoSync
  RosToGodot
    Visuals
      base_link
        wheel_left_link
        wheel_right_link
        base_scan
```

The ROS-to-Godot coordinate conversion used by the generated scene is:

```text
godot_x = -ros_y
godot_y =  ros_z
godot_z = -ros_x
```

## Gallery

### TurtleBot3 Burger — MJCF (MuJoCo Viewer)
![TB3 Burger in MuJoCo](docs/images/tb3_burger_mjcf.png)

### TurtleBot3 Burger — GLB (3D Scene)
![TB3 Burger GLB](docs/images/tb3_burger_glb.png)

### TurtleBot3 Burger — Split Parts (GLB)
![TB3 Burger parts](docs/images/tb3_burger_parts.png)

## Registered Robots

| Name | Source | Formats | License |
|---|---|---|---|
| TurtleBot3 (TB3) | [ROBOTIS-GIT/turtlebot3](https://github.com/ROBOTIS-GIT/turtlebot3) | URDF, MJCF, GLB | Apache License 2.0 |

## Status & TODO

### Done
- [x] Repository created
- [x] Directory structure defined
- [x] `sources/tb3.yaml` — TB3 fetch definition
- [x] `tools/fetch.py` — sparse fetch from upstream repos
- [x] `tools/xacro2urdf.py` — ROS-free xacro → URDF conversion
- [x] `tools/urdf2mjcf.py` — URDF → MJCF conversion via MuJoCo
- [x] `tools/urdf2glb.py` — URDF → GLB conversion
- [x] `tools/mjcf2glb.py` — MJCF → split GLB conversion
- [x] `tools/mjcf_add_actuators.py` — actuator YAML → actuated MJCF conversion
- [x] `tools/mjcf2pdu.py` — MJCF body list → Hakoniwa pdutypes.json conversion
- [x] TB3 の変換検証（MJCF, GLB）

### In Progress
- [ ] `tools/forge.sh` — full pipeline runner improvements

### Planned
- [ ] CI/CD: push 時に自動変換・成果物アップロード
- [ ] 追加ロボットの登録

## License

MIT
