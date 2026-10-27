#!/usr/bin/env bash
# Builds the SailingPhysics sources standalone (no Unreal) and runs the J/22 polar sweep.
# Seconds instead of minutes, for tuning the physics. Usage: scripts/polar.sh [--boat b] [--ar c] [--surf s] [--flow f]
# [--quick | --scenarios | --easy | --point <tws> <twa> | --sea [gale | checks | surf | trim | orc <hs> <tws> | at <tws> <twa>]]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/polar-sweep"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/PolarSweep/main.cpp" -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$@"
