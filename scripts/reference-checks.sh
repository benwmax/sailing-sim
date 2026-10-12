#!/usr/bin/env bash
# Builds the SailingPhysics sources standalone (no Unreal) and runs the Phase 8 physics checks against real numbers
# (heel tables, tacking angles, roll period, lake waves, capsize behaviour, speed ceilings, Portsmouth ratios).
# Usage: scripts/reference-checks.sh [--quick] [--csv]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/reference-checks"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/ReferenceChecks/main.cpp" -o "$OUT"
"$OUT" "$@"
