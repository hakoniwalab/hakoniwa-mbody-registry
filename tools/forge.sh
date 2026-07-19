#!/bin/bash

set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <path_to_yaml_file> <entry_urdf_relative_to_source>"
    exit 1
fi

YAML_FILE="$1"
ENTRY_URDF_REL="$2"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "${HAKO_SKIP_FETCH:-0}" = "1" ]; then
    echo "Skipping fetch because HAKO_SKIP_FETCH=1"
else
    python3 "$SCRIPT_DIR/fetch.py" "$YAML_FILE"
fi

ROBOT_NAME="$(python3 - <<'PY' "$YAML_FILE"
from pathlib import Path
import sys
import yaml
config = yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(config["name"])
PY
)"

SOURCE_URDF="$REPO_ROOT/bodies/$ROBOT_NAME/source/$ENTRY_URDF_REL"
GENERATED_URDF="$REPO_ROOT/bodies/$ROBOT_NAME/generated/$(basename "${ENTRY_URDF_REL%.*}").urdf"
GENERATED_XML="$REPO_ROOT/bodies/$ROBOT_NAME/generated/$(basename "${ENTRY_URDF_REL%.*}").xml"
ACTUATOR_CONFIG="$REPO_ROOT/bodies/$ROBOT_NAME/config/actuators.yaml"
PDU_CONFIG="$REPO_ROOT/bodies/$ROBOT_NAME/config/pdu_bodies.yaml"
PDU_MANIFEST="$REPO_ROOT/bodies/$ROBOT_NAME/config/pdu-manifest.yaml"
MUJOCO_WORLD_CONFIG="$REPO_ROOT/bodies/$ROBOT_NAME/config/mujoco_world.yaml"

python3 "$SCRIPT_DIR/xacro2urdf.py" "$SOURCE_URDF"
python3 "$SCRIPT_DIR/urdf2mjcf.py" "$GENERATED_URDF"
if [ -f "$ACTUATOR_CONFIG" ]; then
    python3 "$SCRIPT_DIR/mjcf_add_actuators.py" "$GENERATED_XML" "$ACTUATOR_CONFIG"
fi
python3 "$SCRIPT_DIR/urdf2glb.py" "$GENERATED_URDF"
python3 "$SCRIPT_DIR/mjcf2glb.py" "$GENERATED_XML"
if [ -f "$PDU_MANIFEST" ]; then
    python3 "$SCRIPT_DIR/pdu_manifest2types.py" "$PDU_MANIFEST"
    python3 "$SCRIPT_DIR/pdu_manifest2def.py" "$PDU_MANIFEST"
elif [ -f "$PDU_CONFIG" ]; then
    python3 "$SCRIPT_DIR/mjcf2pdu.py" "$GENERATED_XML" "$PDU_CONFIG"
fi
if [ -f "$MUJOCO_WORLD_CONFIG" ]; then
    WORLD_INPUT_XML="$GENERATED_XML"
    if [ -f "${GENERATED_XML%.xml}.actuated.xml" ]; then
        WORLD_INPUT_XML="${GENERATED_XML%.xml}.actuated.xml"
    fi
    python3 "$SCRIPT_DIR/mjcf_compose_world.py" "$WORLD_INPUT_XML" "$MUJOCO_WORLD_CONFIG" \
        -o "${GENERATED_XML%.xml}.minimal_world.xml"
fi
