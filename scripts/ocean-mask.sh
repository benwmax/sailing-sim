#!/usr/bin/env bash
# Gulf swell: builds SailingPhysics standalone and maps FOcean's mask (where the swell reaches) on a world's terrain.
# Usage: scripts/ocean-mask.sh [GalvestonBay|GulfPassage] [swell Hs m] [swell from deg]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/ocean-mask"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/OceanMask/main.cpp" -lz -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$@"
