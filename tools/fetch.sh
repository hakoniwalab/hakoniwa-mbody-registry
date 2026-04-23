#!/bin/bash

# A shell script to fetch robot source files based on a YAML definition.
# It uses git sparse-checkout to efficiently download only the specified files.
#
# Usage:
#   ./tools/fetch.sh <path_to_yaml_file>
#
# Example:
#   ./tools/fetch.sh sources/tb3.yaml

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path_to_yaml_file>"
    exit 1
fi

YAML_FILE="$1"
if [ ! -f "$YAML_FILE" ]; then
    echo "Error: YAML file not found at '$YAML_FILE'"
    exit 1
fi

# Simplified YAML parser using grep and sed.
get_yaml_value() {
    grep "^$1:" "$2" | sed "s/^$1: //"
}

NAME=$(get_yaml_value "name" "$YAML_FILE")
REPO=$(get_yaml_value "repo" "$YAML_FILE")
BRANCH=$(get_yaml_value "branch" "$YAML_FILE")

# The output directory for the fetched files.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST_DIR="$REPO_ROOT/bodies/$NAME"

echo "Fetching robot source for: $NAME"
echo "  - Repo:        $REPO"
echo "  - Branch:      $BRANCH"
echo "  - Destination: $DEST_DIR"

# Clean up previous fetches if they exist.
if [ -d "$DEST_DIR" ]; then
    echo "  - Cleaning up existing directory: $DEST_DIR"
    rm -rf "$DEST_DIR"
fi
mkdir -p "$DEST_DIR"

# Perform a sparse checkout in a temporary directory.
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

git -C "$TMP_DIR" init -q
git -C "$TMP_DIR" remote add origin "$REPO"

# Get the list of file paths for sparse checkout.
FILE_PATHS=()
while IFS= read -r line; do
    FILE_PATHS+=("$line")
done < <(grep -E '^\s*-\s*' "$YAML_FILE" | sed 's/^\s*-\s*//' | sed 's/\/$//')

echo "  - Setting up sparse checkout for:"
printf '      %s\n' "${FILE_PATHS[@]}"

git -C "$TMP_DIR" sparse-checkout init --cone
git -C "$TMP_DIR" sparse-checkout set "${FILE_PATHS[@]}"

# Pull the specified files.
echo "  - Pulling files from branch '$BRANCH'..."
git -C "$TMP_DIR" pull --depth=1 origin "$BRANCH"

# Move fetched files to the destination directory (excluding .git/).
find "$TMP_DIR" -maxdepth 1 ! -name '.' ! -name '.git' -exec mv {} "$DEST_DIR/" \;

echo "Fetch complete. Files are in $DEST_DIR"
echo "Fetched files:"
ls -R "$DEST_DIR"

exit 0