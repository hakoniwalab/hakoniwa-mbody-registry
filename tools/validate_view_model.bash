#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 tools/validate_view_model_recipe.py \
  --schema schemas/view-model-recipe.schema.json \
  bodies/turtlebot3/config/viewer.recipe.yaml

python3 tools/validate_view_model.py \
  --schema schemas/view-model.schema.json \
  bodies/turtlebot3/view/turtlebot3.json
