#!/usr/bin/env bash
# The frigate Commonwealth's trial sail (docs/frigate-physics): builds the SailingPhysics sources standalone with her
# trial config from a build dir (physics.py's CommonwealthHullData.inl and commonwealth_trial.inl) and sails her. Usage:
#   Tools/shipkit/frigate/trial/trial.sh <build dir> [--quick | --point <tws> <twa> [plan] | --manoeuvre <tack|wear|heaveto> <tws> [plan] | --astern <helm>]
# (PROBE_AT=<s> with --manoeuvre tries her 60 s on from that moment with one thing changed at a time.)
# Writes <build dir>/trial.json. A minute or two; no Unreal (as scripts/polar.sh).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
BUILD="$(cd "$1" && pwd)"
shift
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$BUILD/trial_sail"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
CXX="${CXX:-clang++}"
"$CXX" -std=c++17 -O2 -pthread -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" -I"$BUILD" $SOURCES "$REPO_ROOT/Tools/shipkit/frigate/trial/trial_sail.cpp" -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$BUILD/trial.json" "$@"
