#!/usr/bin/env bash
# Builds the SailingPhysics sources standalone (no Unreal) and checks a session's gusts against its label the way a sailor
# reads "10 gusting 13", and that the chosen wind holds (Tools/GustCheck). Needs the real Content/TerrainData/Wind.mann
# (git lfs pull), not its LFS stub. Usage: scripts/gust-check.sh [--hours h]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/gust-check"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/GustCheck/main.cpp" -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$@"
