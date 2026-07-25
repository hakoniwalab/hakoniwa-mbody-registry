# MBody Registry Responsibility Boundary

This document records the responsibility boundary of `hakoniwa-mbody-registry` after cross-repository validation through Hakoniwa Business Pack recipes and real robot integrations.

## Current responsibility

`hakoniwa-mbody-registry` owns reproducible robot-body preparation and target artifact generation.

It does not own runtime behavior.

```text
Upstream robot source
  -> source materialization
  -> body normalization / adaptation
  -> canonical body artifacts
  -> target-specific generated artifacts
  -> downstream runtime
```

The repository may generate artifacts for a downstream runtime when the generation can be expressed reproducibly from versioned source/configuration. The downstream repository remains responsible for interpreting and executing those artifacts at runtime.

## Core body-preparation responsibilities

The following are core MBody responsibilities:

- versioned source definitions under `sources/`
- upstream source materialization from pinned revisions
- Xacro / URDF normalization
- direct MJCF materialization when upstream already provides an authoritative MJCF tree
- mesh preprocessing required to make a body description consumable
- canonical structural MJCF generation
- GLB / per-part visual asset generation
- runtime-neutral view-model generation
- validation of generated or materialized body assets

Recent integrations show that this preparation layer needs to handle more than file-format conversion. Tracer required DAE-to-OBJ preprocessing and collision/contact adaptation, while Shadow Hand required reproducible direct-MJCF materialization with recursive asset validation.

## Target-specific artifact generators are allowed

Target-specific generation is allowed when MBody remains a build-time producer rather than the owner of runtime behavior.

### MuJoCo-targeted exports

Examples:

- actuator injection into generated MJCF
- collision primitive overlays
- contact excludes
- minimal-world composition for validation or handoff

These outputs prepare a body for a MuJoCo consumer. Runtime control semantics, lifecycle, simulation execution, PDU handling, and controller behavior remain downstream responsibilities such as `hakoniwa-mujoco-robots`.

### Godot-targeted exports

Examples:

- `.tscn` scene generation
- endpoint configuration generation
- `robot_sync.profile.json` generation

These outputs package robot-specific information for `hakoniwa-godot`. Godot addon behavior, runtime connection handling, scene execution, and synchronization behavior remain owned by `hakoniwa-godot`.

### PDU-related exports

Examples:

- canonical `pdutypes.json` generation from `pdu-manifest.yaml`
- compact `pdu_def.json` generation

These are declarative connection artifacts. Runtime endpoint behavior and transport execution remain outside MBody.

## Boundary test

Use this test when deciding where a tool belongs:

```text
Does this tool reproducibly derive an artifact from robot-body source/config?
  -> MBody may own it.

Does this code execute or own runtime behavior, lifecycle, transport, control,
physical actuation, or engine-specific runtime policy?
  -> downstream runtime should own it.
```

Artifact generation and runtime semantic ownership are intentionally treated as different concerns.

## Tool classification

### Core

- `fetch.py`
- `xacro2urdf.py`
- `urdf2mjcf.py`
- `urdf2glb.py`
- `mjcf2glb.py`
- `hako_viewer_model_gen.py`
- mesh/source preprocessing helpers
- body/materialization validators

### Target exporters

- `mjcf_add_actuators.py`
- `mjcf_apply_collision_primitives.py`
- `mjcf_add_contact_excludes.py`
- `mjcf_compose_world.py`
- `pdu_manifest2types.py`
- `pdu_manifest2def.py`
- `godot_sync2endpoint.py`
- `godot_sync2profile.py`
- `hako_godot_scene_gen.py`

Target exporters should remain declarative and reproducible. They should not accumulate runtime execution logic.

### Legacy / review candidates

- `mjcf2pdu.py`
  - retained only for compatibility while canonical PDU generation uses `pdu-manifest.yaml`

Other old installers, staging helpers, generated examples, or one-off scripts should be reviewed individually rather than moved solely because they are target-specific.

## Cross-repository validation as architecture evidence

Hakoniwa Business Pack recipes are useful architecture tests because they validate actual handoff boundaries across repositories.

Examples:

- Tracer validates the flow from external Xacro/URDF through MBody normalization and MuJoCo-targeted preparation into `hakoniwa-mujoco-robots` runtime control.
- Shadow Hand validates pinned direct-MJCF materialization and asset closure before the model is consumed downstream.
- Godot/TB3 validation separates generated robot-specific scene/profile artifacts from the Godot runtime implementation that consumes them.

When these workflows reveal a mismatch between documentation and actual behavior, update both the source repository documentation and the Business Pack knowledge that describes it.

## Maintenance rule

Do not refactor a tool into another repository merely because its output is engine-specific.

Refactor or move it when one of these becomes true:

1. it starts owning runtime behavior rather than artifact generation;
2. it requires runtime state or engine lifecycle to operate;
3. its configuration is no longer robot/body-derived and is primarily application/runtime policy;
4. duplicated ownership creates incompatible sources of truth;
5. cross-repository validation shows that the current ownership prevents a clean handoff.

Otherwise prefer preserving a reproducible single entry point for preparing robot assets.
