# hakoniwa-mbody-registry

Robot body definitions as molds — convert to URDF, MJCF, and GLB for Hakoniwa simulations.

## Overview

`hakoniwa-mbody-registry` is a **ROS-independent** registry of robot physical body definitions (mold-bodies) for the [Hakoniwa](https://github.com/hakoniwalab) simulation ecosystem.

It is the physical counterpart to [`hakoniwa-pdu-registry`](https://github.com/hakoniwalab/hakoniwa-pdu-registry):

| Repository | Role |
|---|---|
| `hakoniwa-pdu-registry` | Data communication type definitions (ROS IDL-based) |
| `hakoniwa-mbody-registry` | Robot physical body definitions (xacro-based) |

Each robot body is defined as a **mold** (mbody) — a xacro-based source definition that can be cast into multiple simulation formats.

## Toolchain

```
xacro  →  URDF  →  MJCF
                →  GLB
```

All conversion tools are bundled in `tools/` and operate without a ROS installation.

## Dependencies

The tools require these Python packages:

```bash
python3 -m pip install -r requirements.txt
```

## Repository Structure

```
hakoniwa-mbody-registry/
├── tools/
│   ├── fetch.py          # Fetch robot source files from upstream repos
│   ├── xacro2urdf.py     # xacro → URDF
│   ├── urdf2mjcf.py      # URDF → MJCF
│   ├── urdf2glb.py       # URDF → GLB
│   └── forge.sh          # Full pipeline: fetch → xacro → URDF → MJCF/GLB
├── bodies/               # Fetched/generated files (not committed to Git)
│   └── .gitkeep
├── sources/              # Declarative fetch definitions per robot
│   └── tb3.yaml          # TurtleBot3
└── README.md
```

### `sources/` — Fetch Definitions

Each YAML file declares where to fetch robot source files from and which paths to retrieve:

```yaml
name: turtlebot3
repo: https://github.com/ROBOTIS-GIT/turtlebot3
branch: main
files:
  - turtlebot3_description/urdf/
  - turtlebot3_description/meshes/
```

Running `tools/fetch.py` reads these files and performs a sparse checkout of only the listed paths into `bodies/{name}/`, preserving the upstream relative paths.

`tools/urdf2mjcf.py` uses the official MuJoCo Python bindings to load URDF and save canonical MJCF. If the URDF contains `package://...` mesh references, the tool rewrites them to local relative paths before invoking MuJoCo. When the package root cannot be inferred from the input path, pass `--package-root PACKAGE=PATH`.

## Quick Start

```bash
# 1. Fetch robot source files
python3 tools/fetch.py sources/tb3.yaml

# 2. Run full pipeline
./tools/forge.sh sources/tb3.yaml
```

Output is generated under `bodies/{name}/generated/`.

## Registered Robots

| Name | Source | Formats |
|---|---|---|
| TurtleBot3 (TB3) | [ROBOTIS-GIT/turtlebot3](https://github.com/ROBOTIS-GIT/turtlebot3) | URDF, MJCF, GLB |

## Status & TODO

### Done
- [x] Repository created
- [x] Directory structure defined
- [x] `sources/tb3.yaml` — TB3 fetch definition

### In Progress
- [x] `tools/fetch.py` — sparse fetch from upstream repos
- [x] `tools/xacro2urdf.py` — ROS-free xacro → URDF conversion
- [x] `tools/urdf2mjcf.py` — URDF → MJCF conversion via MuJoCo
- [ ] `tools/urdf2glb.py` — URDF → GLB conversion
- [ ] `tools/forge.sh` — full pipeline runner

### Planned
- [ ] TB3 の変換検証（MJCF, GLB）
- [ ] CI/CD: push 時に自動変換・成果物アップロード
- [ ] 追加ロボットの登録

## License

MIT
