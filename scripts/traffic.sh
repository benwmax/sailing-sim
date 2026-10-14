#!/usr/bin/env bash
# Builds Source/SailingPhysics standalone with clang (no Unreal) and runs the Navigation Rules scenarios in seconds.
# Usage: scripts/traffic.sh [scenario index (prints its events)]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/traffic-scenarios"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/TrafficScenarios/main.cpp" -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$@"
