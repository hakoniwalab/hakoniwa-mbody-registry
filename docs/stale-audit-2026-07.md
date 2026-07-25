# Stale Knowledge and Tool Audit — 2026-07

This audit was triggered by Issue #2 after cross-repository validation through Hakoniwa Business Pack exposed that the repository's actual responsibility boundary had become clearer than some older documentation.

The goal is not to delete or move tools aggressively. The goal is to distinguish:

- current supported behavior;
- stale documentation;
- legacy compatibility helpers;
- target exporters that still belong here;
- true runtime responsibility leaks that should move downstream.

## Confirmed stale documentation

### README: Xacro `$(find ...)` behavior

Older README text says `xacro2urdf.py` detects ROS-style `$(find ...)` and fails early.

Current behavior is broader: explicit `--package NAME=PATH` mappings can resolve supported `$(find PACKAGE)` expressions without installing ROS.

Action:

- update the README description and examples to point to `docs/xacro-package-mapping.md`;
- update Business Pack recipes that still describe all `$(find ...)` usage as requiring source adaptation.

### README: `forge.sh` scope

Older README text says newer PDU/Godot generators are not integrated into `forge.sh` and calls integration the next step.

Current `forge.sh` already performs more than the old description, including optional PDU generation, actuator/collision/contact processing, minimal-world composition, and a direct `mjcf_passthrough` materialization mode.

Action:

- rewrite the `forge.sh` section around current modes and current optional stages;
- avoid claiming that all target exporters are part of one monolithic forge path when some Godot exports are still separate commands.

### README: registered robots

The registered-robots table still presents TurtleBot3 as the only registered robot.

Current repository knowledge includes at least additional source definitions and validated flows such as AgileX Tracer and Shadow Hand.

Action:

- regenerate or manually refresh the registered-robot overview from `sources/*.yaml`;
- distinguish converted/committed registry outputs from source-materialization-only entries.

## Tool classification audit

### Keep as core

- `fetch.py`
- `xacro2urdf.py`
- `urdf2mjcf.py`
- `urdf2glb.py`
- `mjcf2glb.py`
- `hako_viewer_model_gen.py`
- DAE/OBJ and source-normalization helpers
- `validate_mjcf_assets.py` and view-model validators

Rationale: these tools prepare, normalize, materialize, or validate robot-body artifacts.

### Keep as target exporters

- `mjcf_add_actuators.py`
- `mjcf_apply_collision_primitives.py`
- `mjcf_add_contact_excludes.py`
- `mjcf_compose_world.py`
- `pdu_manifest2types.py`
- `pdu_manifest2def.py`
- `godot_sync2endpoint.py`
- `godot_sync2profile.py`
- `hako_godot_scene_gen.py`

Rationale: these derive reproducible downstream-consumable artifacts from robot/body configuration. Their presence does not make MBody the runtime owner.

Audit condition: keep them declarative. If one begins to require runtime lifecycle/state or to implement engine behavior, move that behavior downstream.

### Legacy / deprecation candidate

#### `mjcf2pdu.py`

The README already describes this as a legacy body-list-oriented helper and recommends `pdu-manifest.yaml` with `pdu_manifest2types.py` and `pdu_manifest2def.py` for canonical robot PDU definitions.

Action before deletion:

1. search all repository docs/config/examples for references;
2. search Business Pack recipes for references;
3. mark deprecated with a replacement path if references remain;
4. delete only after downstream consumers are confirmed absent or migrated.

### Needs individual review

- old Godot installers/staging helpers;
- hand-written reference scenes/scripts that may now be superseded by generators;
- old generated artifacts whose source/config can no longer reproduce them;
- compatibility aliases retained after naming/schema changes.

Do not remove these based only on age. First establish whether they are still used as golden/reference data, compatibility paths, or validation fixtures.

## Business Pack synchronization audit

Cross-repository validation is now a second source of evidence for architecture and behavior, but Business Pack knowledge can itself become stale.

Known follow-up areas:

- refresh `catalog/components/hakoniwa-mbody-registry.yaml` against the current MBody main revision;
- update the Tracer recipe's Xacro/package-mapping notes;
- record direct-MJCF materialization and asset-closure validation as MBody capabilities;
- distinguish body preparation from downstream runtime validation in every Recipe;
- review any Recipe that treats an old workaround as a permanent architectural constraint.

## Refactoring order

Use this order to avoid breaking verified workflows:

1. establish and document the responsibility boundary;
2. correct stale README/docs statements;
3. refresh Business Pack Catalog/Recipes from current evidence;
4. identify truly legacy tools by reference search;
5. deprecate before deleting when external consumers may exist;
6. re-run representative cross-repository Recipes;
7. remove or move only the code that violates the clarified boundary.

## Representative regression flows

The following flows should be treated as architecture regression tests:

### TurtleBot3

- Xacro/URDF source materialization
- structural MJCF
- GLB parts
- view-model
- Godot generated artifacts and downstream consumption

### AgileX Tracer

- pinned source definition
- Xacro/URDF normalization
- DAE-to-OBJ preprocessing
- structural MJCF
- actuator/collision/contact overlays
- minimal-world handoff
- downstream MuJoCo/Hakoniwa runtime control

### Shadow Hand

- pinned MuJoCo Menagerie source
- `mjcf_passthrough`
- recursive include/mesh materialization
- downstream consumption without committing third-party mesh assets

## Completion criteria for Issue #2

Issue #2 should be considered complete when:

- the responsibility boundary is documented as artifact preparation/export vs runtime ownership;
- README and active docs match current tool behavior;
- target-specific generators are deliberately classified rather than automatically moved;
- legacy helpers have explicit replacement/deprecation status;
- Business Pack knowledge has been refreshed from current MBody evidence;
- TurtleBot3, Tracer, and Shadow Hand representative flows still validate the intended handoff boundaries;
- no remaining tool clearly owns downstream runtime behavior inside MBody.
