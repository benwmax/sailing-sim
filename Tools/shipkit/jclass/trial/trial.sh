#!/usr/bin/env bash
# Bluebonnet's trial sail (slice 13): builds the SailingPhysics sources standalone with her trial config from a build
# dir (physics.py's BluebonnetHullData.inl and bluebonnet_trial.inl) and sails her. Usage:
#   Tools/shipkit/jclass/trial/trial.sh <build dir> [--quick]
# Writes <build dir>/trial.json. Seconds to a few minutes; no Unreal (as scripts/polar.sh).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
BUILD="$(cd "$1" && pwd)"
shift
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$BUILD/trial_sail"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
CXX="${CXX:-clang++}"
"$CXX" -std=c++17 -O2 -pthread -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" -I"$BUILD" $SOURCES "$REPO_ROOT/Tools/shipkit/jclass/trial/trial_sail.cpp" -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$BUILD/trial.json" "$@"
