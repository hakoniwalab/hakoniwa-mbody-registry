#!/bin/bash


GODOT_PROJECT_PATH=${GODOT_PROJECT_PATH:-"../../../godot/hakoniwa-tb-3"}
PARTS_PATH=${PARTS_PATH:-"bodies/turtlebot3/generated/parts"}
GODOT_ASSETS_PATH=${GODOT_ASSETS_PATH:-"bodies/turtlebot3/godot_tb3_reference"}
ls ${GODOT_PROJECT_PATH}
ls ${PARTS_PATH}
ls ${GODOT_ASSETS_PATH}

rm -rf ${GODOT_PROJECT_PATH}/parts
mkdir -p ${GODOT_PROJECT_PATH}/assets
cp -rp ${PARTS_PATH} ${GODOT_PROJECT_PATH}/assets/
cp -rp ${GODOT_ASSETS_PATH}/* ${GODOT_PROJECT_PATH}/assets/
