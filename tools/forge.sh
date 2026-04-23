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

python3 "$SCRIPT_DIR/fetch.py" "$YAML_FILE"

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

python3 "$SCRIPT_DIR/xacro2urdf.py" "$SOURCE_URDF"
python3 "$SCRIPT_DIR/urdf2mjcf.py" "$GENERATED_URDF"
python3 "$SCRIPT_DIR/urdf2glb.py" "$GENERATED_URDF"
python3 "$SCRIPT_DIR/mjcf2glb.py" "$GENERATED_XML"
