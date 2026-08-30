# Generic Ackermann Golf Cart body

This directory is the source of truth for the generic Ackermann body.

- `model.xml`: structural and visual MJCF without a world or actuators
- `actuators.yaml`: steering and rear-wheel MuJoCo actuators
- `collision_primitives.yaml`: chassis and narrow physical tire proxies
- `contact_excludes.yaml`: intentional assembly self-contact exclusions
- `mujoco_world.yaml`: reproducible minimal test world
- `provenance.yaml`: origin, license, and design references

Generate all derived MJCF files with:

```bash
python tools/ackermann/forge.py generic_ackermann_golf_cart
python tools/ackermann/forge.py generic_ackermann_golf_cart --verify
python tools/ackermann/validate.py generic_ackermann_golf_cart
```

The generated runtime model is:

```text
bodies/generic_ackermann_golf_cart/generated/model.minimal_world.xml
```

Do not hand-edit generated XML. Adjust the structural MJCF or YAML inputs and
run the Forge again.

## Ownership boundary

This registry owns the body and reproducible MuJoCo preparation inputs:

- structure, visuals, mass, joints, and inertial properties
- MuJoCo actuator definitions and gains
- collision proxies and intentional contact exclusions
- the minimal validation world

`hakoniwa-mujoco-robots` owns runtime semantics:

- the asset adapter and simulation lifecycle
- PDU definitions and endpoint bindings
- actuator component bindings and update rates
- Ackermann command conversion, PS5 mapping, and Launcher orchestration

The downstream asset manifest points at the generated model. It must not copy
or hand-edit this model.

## Validation

The Forge is deterministic for the versioned inputs. After regeneration, load
the final model with MuJoCo and run the downstream strong check:

```bash
cd ../hakoniwa-mujoco-robots
python3.12 tools/recipe/generic_ackermann.py build
python3.12 tools/recipe/generic_ackermann.py check
```

The MBody headless check covers idle stability, straight travel, both turn
directions, actual inner/outer steering angles, rear-wheel differential speed,
left/right symmetry, numerical stability, and RTF. The downstream check covers
the Hakoniwa adapter integration. Neither validates gamepad ergonomics or
Viewer rendering smoothness; those remain manual runtime acceptance steps.
