#!/usr/bin/env bash
# Wildlife Phase 1: builds SailingPhysics standalone and runs the distant birds on each world's real terrain (counts against
# the tables, band budgets, flushes, update time). Usage: scripts/wildlife-check.sh [World|all] [--months 1,4,7,10]
# [--hour 10] [--minutes 10] [--sail] [--tier 2] [--spot N] [--species] [--scale <density>]
# Needs the worlds' .height (and TexasCoast.tiles) from Git LFS.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/wildlife-check"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/WildlifeCheck/main.cpp" -lz -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$@"
