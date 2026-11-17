#!/usr/bin/env bash
# Cannon fire standalone (docs/cannon-fire/): builds SailingPhysics with clang (no Unreal) and runs Tools/CannonCheck.
# Usage: scripts/cannon-check.sh [--drill | --recoil | --smoke [seconds] [--wind m/s] [--budget n] | --params] [--fx "Key=V,..."]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/cannon-check"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/CannonCheck/main.cpp" -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$@"
