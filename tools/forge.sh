#!/bin/bash

set -euo pipefail

if [ "$#" -ne 2 ] && [ "$#" -ne 3 ]; then
    echo "Usage:"
    echo "  New:    $0 <path_to_yaml_file> <output_dir> [<entry_urdf_relative_to_source>]"
    echo "  Legacy: $0 <path_to_yaml_file> <entry_urdf_relative_to_source>"
    exit 1
fi

YAML_FILE="$1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

#
# Read robot configuration.
#
# The default forge mode preserves the existing URDF/Xacro -> MJCF pipeline.
# mjcf_passthrough materializes an upstream MJCF tree and validates its local
# include/mesh references without converting it.
#
eval "$(python3 - <<'PY' "$YAML_FILE"
from pathlib import Path
import shlex
import sys
import yaml

config = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
forge = config.get("forge", {})

def emit(name, value):
    print(f"{name}={shlex.quote(str(value))}")

emit("ROBOT_NAME", config["name"])
emit("FORGE_MODE", forge.get("mode", "urdf_to_mjcf"))
emit("YAML_ENTRY_URDF_REL", forge.get("entry_urdf", ""))
emit("YAML_ENTRY_MJCF_REL", forge.get("entry_mjcf", ""))
emit("SOURCE_DISCARD_VISUAL", "1" if forge.get("urdf2mjcf", {}).get("discard_visual", False) else "0")
emit("SOURCE_DAE2OBJ_ENABLED", "1" if forge.get("urdf_dae2obj", {}).get("enabled", False) else "0")
PY
)"

case "$FORGE_MODE" in
    urdf_to_mjcf|mjcf_passthrough)
        ;;
    *)
        echo "Error: unsupported forge.mode '$FORGE_MODE'."
        echo "Supported modes: urdf_to_mjcf, mjcf_passthrough"
        exit 1
        ;;
esac

#
# Direct MJCF materialization.
#
# This mode intentionally writes upstream source assets to the caller-provided
# output directory. For external meshes that should not be committed, use the
# ignored bodies/<name>/source directory.
#
if [ "$FORGE_MODE" = "mjcf_passthrough" ]; then
    if [ "$#" -ne 2 ]; then
        echo "Error: mjcf_passthrough expects exactly:"
        echo "  $0 <path_to_yaml_file> <output_dir>"
        exit 1
    fi
    if [ -z "$YAML_ENTRY_MJCF_REL" ]; then
        echo "Error: forge.entry_mjcf is required for mjcf_passthrough."
        exit 1
    fi

    OUTPUT_DIR="$2"
    mkdir -p "$OUTPUT_DIR"
    OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

    if [ "${HAKO_SKIP_FETCH:-0}" = "1" ]; then
        echo "Skipping fetch because HAKO_SKIP_FETCH=1"
    else
        python3 "$SCRIPT_DIR/fetch.py" \
            "$YAML_FILE" \
            --output-dir "$OUTPUT_DIR"
    fi

    ENTRY_MJCF="$OUTPUT_DIR/$YAML_ENTRY_MJCF_REL"
    if [ ! -f "$ENTRY_MJCF" ]; then
        echo "Error: Entry MJCF not found at $ENTRY_MJCF"
        exit 1
    fi

    echo "Forging robot: $ROBOT_NAME"
    echo "  - Mode:        $FORGE_MODE"
    echo "  - Entry MJCF:  $ENTRY_MJCF"
    echo "  - Materialized: $OUTPUT_DIR"

    python3 "$SCRIPT_DIR/validate_mjcf_assets.py" "$ENTRY_MJCF"

    echo "Forge complete."
    echo "Materialized MJCF source is in: $OUTPUT_DIR"
    exit 0
fi

#
# Resolve URDF mode and arguments.
#
# New style:
#   forge.sh source.yaml generated_dir
#   -> entry_urdf comes from forge.entry_urdf
#
# New style with override:
#   forge.sh source.yaml generated_dir entry_urdf
#
# Legacy style:
#   forge.sh source.yaml entry_urdf
#   -> source: bodies/<name>/source
#   -> output: bodies/<name>/generated
#
if [ "$#" -eq 3 ]; then
    MODE="new"
    GENERATED_DIR="$2"
    ENTRY_URDF_REL="$3"

elif [ -n "$YAML_ENTRY_URDF_REL" ]; then
    MODE="new"
    GENERATED_DIR="$2"
    ENTRY_URDF_REL="$YAML_ENTRY_URDF_REL"

else
    MODE="legacy"
    ENTRY_URDF_REL="$2"
    GENERATED_DIR="$REPO_ROOT/bodies/$ROBOT_NAME/generated"
fi

if [ -z "$ENTRY_URDF_REL" ]; then
    echo "Error: entry URDF is not defined."
    echo "Set forge.entry_urdf in $YAML_FILE or pass it as an argument."
    exit 1
fi

#
# Prepare generated directory.
#
mkdir -p "$GENERATED_DIR"
GENERATED_DIR="$(cd "$GENERATED_DIR" && pwd)"

#
# Fetch robot source.
#
if [ "${HAKO_SKIP_FETCH:-0}" = "1" ]; then
    echo "Skipping fetch because HAKO_SKIP_FETCH=1"
else
    if [ "$MODE" = "new" ]; then
        # Fetch source tree directly into generated directory.
        python3 "$SCRIPT_DIR/fetch.py" \
            "$YAML_FILE" \
            --output-dir "$GENERATED_DIR"
    else
        # Fetch into bodies/<name>/source.
        python3 "$SCRIPT_DIR/fetch.py" \
            "$YAML_FILE"
    fi
fi

#
# Resolve source and config paths.
#
ROBOT_ROOT="$REPO_ROOT/bodies/$ROBOT_NAME"

if [ "$MODE" = "new" ]; then
    SOURCE_URDF="$GENERATED_DIR/$ENTRY_URDF_REL"
else
    SOURCE_URDF="$ROBOT_ROOT/source/$ENTRY_URDF_REL"
fi

if [ ! -f "$SOURCE_URDF" ]; then
    echo "Error: Entry URDF not found at $SOURCE_URDF"
    exit 1
fi

#
# Preserve the directory containing the entry URDF.
#
ENTRY_DIR="$(dirname "$ENTRY_URDF_REL")"
ENTRY_FILENAME="$(basename "$ENTRY_URDF_REL")"
ENTRY_BASENAME="${ENTRY_FILENAME%.*}"

if [ "$MODE" = "new" ]; then
    GENERATED_URDF="$GENERATED_DIR/$ENTRY_DIR/$ENTRY_BASENAME.urdf"
else
    GENERATED_URDF="$GENERATED_DIR/$ENTRY_BASENAME.urdf"
fi

GENERATED_XML="$GENERATED_DIR/$ENTRY_BASENAME.xml"

#
# Existing mbody-registry configuration.
# These remain under bodies/<name>/config for backward compatibility.
#
ACTUATOR_CONFIG="$ROBOT_ROOT/config/actuators.yaml"
COLLISION_PRIMITIVES_CONFIG="$ROBOT_ROOT/config/collision_primitives.yaml"
CONTACT_EXCLUDES_CONFIG="$ROBOT_ROOT/config/contact_excludes.yaml"
PDU_CONFIG="$ROBOT_ROOT/config/pdu_bodies.yaml"
PDU_MANIFEST="$ROBOT_ROOT/config/pdu-manifest.yaml"
MUJOCO_WORLD_CONFIG="$ROBOT_ROOT/config/mujoco_world.yaml"

mkdir -p "$(dirname "$GENERATED_URDF")"

echo "Forging robot: $ROBOT_NAME"
echo "  - Mode:           $MODE"
echo "  - Source URDF:    $SOURCE_URDF"
echo "  - Generated URDF: $GENERATED_URDF"
echo "  - Generated MJCF: $GENERATED_XML"

#
# URDF / Xacro -> plain URDF.
#
python3 "$SCRIPT_DIR/xacro2urdf.py" \
    "$SOURCE_URDF" \
    -o "$GENERATED_URDF"

MJCF_INPUT_URDF="$GENERATED_URDF"

if [ "${HAKO_URDF_DAE2OBJ:-$SOURCE_DAE2OBJ_ENABLED}" = "1" ]; then
    GENERATED_OBJ_URDF="${GENERATED_URDF%.urdf}.obj.urdf"
    python3 "$SCRIPT_DIR/urdf_dae2obj.py" \
        "$GENERATED_URDF" \
        -o "$GENERATED_OBJ_URDF"
    MJCF_INPUT_URDF="$GENERATED_OBJ_URDF"
fi

#
# URDF -> MJCF.
#
if [ "${HAKO_URDF2MJCF_DISCARD_VISUAL:-$SOURCE_DISCARD_VISUAL}" = "1" ]; then
    python3 "$SCRIPT_DIR/urdf2mjcf.py" \
        "$MJCF_INPUT_URDF" \
        -o "$GENERATED_XML" \
        --discard-visual
else
    python3 "$SCRIPT_DIR/urdf2mjcf.py" \
        "$MJCF_INPUT_URDF" \
        -o "$GENERATED_XML"
fi

#
# Add actuators if configured.
#
if [ -f "$ACTUATOR_CONFIG" ]; then
    python3 "$SCRIPT_DIR/mjcf_add_actuators.py" \
        "$GENERATED_XML" \
        "$ACTUATOR_CONFIG"
fi

#
# Add primitive collision geoms if configured.
#
COLLISION_INPUT_XML="$GENERATED_XML"
if [ -f "${GENERATED_XML%.xml}.actuated.xml" ]; then
    COLLISION_INPUT_XML="${GENERATED_XML%.xml}.actuated.xml"
fi

if [ -f "$COLLISION_PRIMITIVES_CONFIG" ]; then
    python3 "$SCRIPT_DIR/mjcf_apply_collision_primitives.py" \
        "$COLLISION_INPUT_XML" \
        "$COLLISION_PRIMITIVES_CONFIG"
fi

#
# Add contact excludes if configured.
#
CONTACT_INPUT_XML="$COLLISION_INPUT_XML"
if [ -f "${COLLISION_INPUT_XML%.xml}.collision.xml" ]; then
    CONTACT_INPUT_XML="${COLLISION_INPUT_XML%.xml}.collision.xml"
fi

if [ -f "$CONTACT_EXCLUDES_CONFIG" ]; then
    python3 "$SCRIPT_DIR/mjcf_add_contact_excludes.py" \
        "$CONTACT_INPUT_XML" \
        "$CONTACT_EXCLUDES_CONFIG"
fi

#
# Generate GLB assets.
#
if [ "${HAKO_SKIP_GLB:-0}" = "1" ]; then
    echo "Skipping GLB generation because HAKO_SKIP_GLB=1"
else
    python3 "$SCRIPT_DIR/urdf2glb.py" \
        "$GENERATED_URDF"

    python3 "$SCRIPT_DIR/mjcf2glb.py" \
        "$GENERATED_XML" \
        -o "$GENERATED_DIR/parts"
fi

#
# Generate PDU definitions if configured.
#
if [ -f "$PDU_MANIFEST" ]; then
    python3 "$SCRIPT_DIR/pdu_manifest2types.py" \
        "$PDU_MANIFEST" \
        -o "$GENERATED_DIR/pdutypes.json"

    python3 "$SCRIPT_DIR/pdu_manifest2def.py" \
        "$PDU_MANIFEST" \
        -o "$GENERATED_DIR/pdu_def.json"
elif [ -f "$PDU_CONFIG" ]; then
    python3 "$SCRIPT_DIR/mjcf2pdu.py" \
        "$GENERATED_XML" \
        "$PDU_CONFIG" \
        -o "$GENERATED_DIR/pdutypes.json"
fi

#
# Compose minimal MuJoCo world if configured.
#
if [ -f "$MUJOCO_WORLD_CONFIG" ]; then
    WORLD_INPUT_XML="$GENERATED_XML"

    if [ -f "${GENERATED_XML%.xml}.actuated.xml" ]; then
        WORLD_INPUT_XML="${GENERATED_XML%.xml}.actuated.xml"
    fi

    if [ -f "${WORLD_INPUT_XML%.xml}.collision.xml" ]; then
        WORLD_INPUT_XML="${WORLD_INPUT_XML%.xml}.collision.xml"
    fi

    if [ -f "${WORLD_INPUT_XML%.xml}.contact.xml" ]; then
        WORLD_INPUT_XML="${WORLD_INPUT_XML%.xml}.contact.xml"
    fi

    python3 "$SCRIPT_DIR/mjcf_compose_world.py" \
        "$WORLD_INPUT_XML" \
        "$MUJOCO_WORLD_CONFIG" \
        -o "${GENERATED_XML%.xml}.minimal_world.xml"
fi

echo "Forge complete."
echo "Generated artifacts are in: $GENERATED_DIR"
