[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/hakoniwalab/hakoniwa-mbody-registry)

# hakoniwa-mbody-registry

> Reproducible robot-body preparation and target artifact generation for the Hakoniwa simulation ecosystem.

`hakoniwa-mbody-registry` takes upstream robot descriptions and turns them into stable, reviewable artifacts that downstream simulators and visualizers can consume.

It supports both ROS-origin descriptions such as Xacro / URDF and authoritative MJCF sources. The repository is intentionally **not** a runtime simulator.

## Responsibility Boundary

The current responsibility boundary is:

```text
Upstream robot source
  -> source materialization
  -> body normalization / adaptation
  -> canonical body artifacts
  -> target-specific generated artifacts
  -> downstream runtime
```

MBody owns the preparation side:

- reproducible source definitions under `sources/`
- pinned upstream revisions when needed
- local source materialization
- Xacro / URDF normalization
- direct MJCF materialization
- mesh preprocessing
- structural MJCF generation
- GLB / parts GLB generation
- runtime-neutral view-model generation
- target-specific artifact generation for MuJoCo, PDU, and Godot consumers

Downstream repositories own runtime behavior:

- simulator lifecycle and stepping
- controller semantics and runtime actuation
- PDU transport and runtime connection behavior
- time synchronization behavior
- Godot addon / scene runtime behavior
- runtime-specific policy and orchestration

The important distinction is:

```text
artifact generation        -> MBody can own it
runtime semantic ownership -> downstream runtime owns it
```

See [`docs/responsibility-boundary.md`](docs/responsibility-boundary.md) for the detailed rationale and classification.

## Registry Pattern

This repository follows the same registry idea as `hakoniwa-pdu-registry`:

- `sources/` describes where a robot model comes from and how it should be materialized
- `tools/` contains reusable preparation and export tools
- `bodies/<name>/source/` contains local upstream materialization when required
- `bodies/<name>/generated/` contains generated artifacts intended for downstream consumption
- `bodies/<name>/config/` contains robot-specific preparation / exporter inputs

Generated Hakoniwa-owned artifacts may be committed when that makes downstream use reproducible and reviewable. Third-party upstream assets remain subject to their upstream licenses and are not automatically copied into this repository.

For models whose generated MJCF still references upstream meshes, materialize the source tree locally instead of committing those third-party assets. See [`docs/local-source-materialization.md`](docs/local-source-materialization.md).

## Main Preparation Flows

### Xacro / URDF flow

The default forge mode is `urdf_to_mjcf`.

```text
sources/*.yaml
  -> fetch.py
  -> xacro2urdf.py
  -> optional mesh preprocessing
  -> urdf2mjcf.py
  -> optional MuJoCo target overlays
  -> GLB / parts GLB
  -> optional PDU artifacts
  -> optional minimal MuJoCo world
```

Typical stages currently orchestrated by `tools/forge.sh` include:

- source fetch / materialization
- Xacro or Xacro-enabled URDF expansion
- optional DAE-to-OBJ preprocessing
- structural MJCF generation
- optional actuator injection
- optional primitive collision overlay
- optional contact excludes
- GLB generation
- optional `pdutypes.json` / `pdu_def.json` generation
- optional minimal-world composition

Target-specific exporters are preparation tools. Successful artifact generation does **not** by itself verify downstream runtime control, PDU wiring, or simulation behavior.

### Direct MJCF materialization

Some upstream projects already provide an authoritative MJCF model. In that case, converting through URDF would lose useful source structure or create unnecessary work.

Use `forge.mode: mjcf_passthrough` to materialize the upstream MJCF tree directly and validate its local dependencies.

Representative source definition:

```yaml
name: shadow_hand
repo: https://github.com/google-deepmind/mujoco_menagerie.git
branch: main
revision: 71f066ad0be9cd271f7ed58c030243ef157af9f4
files:
  - shadow_hand/
forge:
  mode: mjcf_passthrough
  entry_mjcf: shadow_hand/scene_right.xml
```

Representative command:

```bash
PATH=$PWD/.venv/bin:$PATH \
  ./tools/forge.sh sources/shadow_hand.yaml bodies/shadow_hand/source
```

This flow intentionally versions the reproducible source definition rather than committing third-party OBJ / STL / DAE assets that can be restored from the pinned upstream revision.

See [`docs/mjcf-passthrough.md`](docs/mjcf-passthrough.md).

### Hakoniwa-authored local MJCF flow

Bodies authored directly for Hakoniwa can keep their structural MJCF and
target overlays together under `bodies/<name>/config/`.  The local Forge then
produces the reviewable runtime artifact without embedding runtime controller
or PDU policy in this repository.

```text
bodies/<name>/config/model.xml
  + actuators.yaml
  + collision_primitives.yaml
  + contact_excludes.yaml
  + mujoco_world.yaml
  -> tools/ackermann/forge.py
  -> bodies/<name>/generated/*.xml
```

The generic Ackermann golf cart is the reference example:

```bash
python tools/ackermann/forge.py generic_ackermann_golf_cart
python tools/ackermann/forge.py generic_ackermann_golf_cart --verify
python tools/ackermann/validate.py generic_ackermann_golf_cart --report /tmp/golf-cart.json
```

See [`bodies/generic_ackermann_golf_cart/config/README.md`](bodies/generic_ackermann_golf_cart/config/README.md).

The same narrow Forge contract also covers an external Xacro/DAE source:

```bash
python tools/ackermann/forge.py hunter_v2
python tools/ackermann/forge.py hunter_v2 --verify
```

`--verify` fetches pinned external sources into a temporary body tree, rebuilds
all artifacts, loads the final MJCF with MuJoCo, and compares every generated
artifact byte-for-byte with the committed registry outputs.

Both bodies use the same Recipe-driven headless migration test suite. See
[`docs/ackermann-validation.md`](docs/ackermann-validation.md). Business Pack
Recipes select the managed Foundation Python; users do not operate an
MBody-local virtual environment for this flow.

## Quick Start: TurtleBot3 Burger

Create a repository-local Python environment first:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Then run the TurtleBot3 Burger forge flow:

```bash
PATH=$PWD/.venv/bin:$PATH \
  ./tools/forge.sh \
  sources/turtlebot3_burger.yaml \
  turtlebot3_description/urdf/turtlebot3_burger.urdf
```

If the source tree is already materialized locally:

```bash
PATH=$PWD/.venv/bin:$PATH \
HAKO_SKIP_FETCH=1 \
  ./tools/forge.sh \
  sources/turtlebot3_burger.yaml \
  turtlebot3_description/urdf/turtlebot3_burger.urdf
```

`HAKO_SKIP_GLB=1` can be used for physics-only checks where GLB generation is unnecessary.

The exact outputs depend on the robot-specific config present under `bodies/<name>/config/`. Typical outputs include:

- plain URDF
- structural MJCF
- optional actuated / collision-overlaid MJCF
- optional minimal-world MJCF
- single or split GLB assets
- optional `pdutypes.json`
- optional `pdu_def.json`

## ROS-free Xacro Package Mapping

`tools/xacro2urdf.py` can expand Xacro files that contain ROS-style `$(find PACKAGE)` references without installing ROS.

Provide package roots explicitly:

```bash
python3 tools/xacro2urdf.py \
  path/to/robot.urdf.xacro \
  -o path/to/robot.urdf \
  --package sr_description=path/to/sr_description \
  --arg hand_version=E3M5 \
  --arg side=right
```

`--package NAME=PATH` may be repeated.

Behavior:

- mapped `$(find NAME)` expressions resolve from explicit package mappings
- no ROS workspace discovery is performed
- unmapped packages fail clearly
- when no `--package` mapping is supplied, Xacro files that require `$(find ...)` still fail early
- generated `package://...` mesh references are left for the downstream conversion stage

See [`docs/xacro-package-mapping.md`](docs/xacro-package-mapping.md).

## Target Exporters

Target exporters are intentionally allowed in this repository when they derive reproducible artifacts from robot-body source/config and do not take ownership of runtime behavior.

### MuJoCo target artifacts

Current tools include preparation such as:

- actuator injection with `tools/mjcf_add_actuators.py`
- primitive collision overlay with `tools/mjcf_apply_collision_primitives.py`
- contact excludes with `tools/mjcf_add_contact_excludes.py`
- minimal-world composition with `tools/mjcf_compose_world.py`

These artifacts can make a body usable by a downstream MuJoCo runner, but runtime actuation, control loops, PDU command handling, and simulation lifecycle belong downstream, for example in `hakoniwa-mujoco-robots`.

A minimal generated world is a preparation artifact, not a guarantee of stable robot dynamics. Friction, contact tuning, sensor layout, controller behavior, and runtime validation remain separate work.

### PDU artifacts

The canonical declarative path is:

```text
pdu-manifest.yaml
  -> pdu_manifest2types.py
  -> pdutypes.json

pdu-manifest.yaml
  -> pdu_manifest2def.py
  -> pdu_def.json
```

These are connection artifacts. Runtime transport and endpoint behavior are not owned here.

`tools/mjcf2pdu.py` is retained only as a **legacy body-list-oriented helper**. New robot definitions should prefer `pdu-manifest.yaml` with `pdu_manifest2types.py` / `pdu_manifest2def.py`. Removal of the legacy helper requires reference and compatibility review first.

### View-model

The runtime-neutral view-model is derived from structural body information and visual assets.

```text
structural MJCF + viewer.recipe.yaml
  -> hako_viewer_model_gen.py
  -> view-model JSON
```

The view-model is deliberately view-only. It does not own PDU channels, endpoint configuration, controller semantics, multi-robot composition, or runtime lifecycle.

See:

- [`docs/view-model.md`](docs/view-model.md)
- [`docs/view-model-recipe.md`](docs/view-model-recipe.md)

### Godot target artifacts

MBody can generate robot-specific artifacts consumed by `hakoniwa-godot`:

```text
view-model JSON
  -> hako_godot_scene_gen.py
  -> .tscn

godot_sync.yaml
  -> godot_sync2endpoint.py
  -> endpoint_shm_with_pdu.json

view-model JSON + godot_sync.yaml
  -> godot_sync2profile.py
  -> robot_sync.profile.json
```

These generators are currently separate from the core `forge.sh` pipeline.

The generated artifacts are preparation-time outputs. `hakoniwa-godot` owns addon behavior, endpoint integration, scene execution, and runtime synchronization behavior.

## Representative Source Definitions

The authoritative inventory is `sources/*.yaml`. Representative flows currently include:

- TurtleBot3 Burger — Xacro / URDF to structural MJCF and GLB
- TurtleBot3 Waffle — URDF/MJCF conversion with source-specific forge options
- AgileX Tracer — pinned `tracer_ros` source, source adaptation, DAE-to-OBJ preprocessing, and MuJoCo target preparation
- Shadow Hand — pinned MuJoCo Menagerie MJCF materialization with include/mesh closure validation

These examples exercise different source shapes. A registered source does not imply every downstream runtime path has been fully verified.

## Runtime Boundary Examples

### MuJoCo

```text
MBody
  -> structural / prepared MJCF artifacts
  -> hakoniwa-mujoco-robots
  -> runtime actuator / controller / PDU behavior
```

### Godot

```text
MBody
  -> GLB / view-model / scene / profile / endpoint config artifacts
  -> hakoniwa-godot
  -> addon / endpoint / scene runtime behavior
```

This separation keeps robot-specific preparation reproducible while preventing MBody from becoming a second runtime implementation.

## Validation and Maintenance

Useful validation and design documents include:

- [`docs/responsibility-boundary.md`](docs/responsibility-boundary.md) — current ownership boundary
- [`docs/stale-audit-2026-07.md`](docs/stale-audit-2026-07.md) — current documentation / legacy audit
- [`docs/local-source-materialization.md`](docs/local-source-materialization.md) — local third-party source materialization
- [`docs/mjcf-passthrough.md`](docs/mjcf-passthrough.md) — direct MJCF flow
- [`docs/xacro-package-mapping.md`](docs/xacro-package-mapping.md) — explicit ROS-free package mapping
- [`docs/view-model.md`](docs/view-model.md) — view-model contract
- [`docs/view-model-recipe.md`](docs/view-model-recipe.md) — human-authored view-model recipe

When a downstream integration exposes a reusable source or artifact problem, prefer fixing the preparation pipeline or adding a declarative source/config input rather than maintaining hand-edited generated model forks.

## License

The repository code is MIT licensed.

Fetched or materialized robot descriptions, meshes, and other third-party assets remain subject to their upstream licenses. A source definition in this repository does not relicense upstream content.
