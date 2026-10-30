#!/usr/bin/env bash
# Renders one sim reel loop through Movie Render Queue (docs/sim-reel/README.md): Tools/reel/capture_reel.py with the
# project's venv (numpy, Pillow). Run scripts/build.sh first: the game runs from the editor binary.
# Usage: scripts/capture-reel.sh <wireframe|fleet|physics|storm|night> [--quality preview|master] [--passes a,b]
#        [--compose-only] [--dry-run];  scripts/capture-reel.sh --list
source "$(dirname "$0")/env.sh"
PY="$REPO_ROOT/Tools/venv/bin/python"
[[ -x "$PY" ]] || PY=python3
exec "$PY" "$REPO_ROOT/Tools/reel/capture_reel.py" "$@"
