#!/usr/bin/env bash
# Builds SailingPhysics standalone and compares the lake's sea (Hs, Tp) with the SWAN bake of Ray Hubbard.
# Usage: scripts/wave-check.sh [swan-compare.csv]  (default: docs/water-3/swan-compare.csv from origin/w3-swan-bake)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/wave-check"
mkdir -p "$REPO_ROOT/Artifacts"
CSV="${1:-}"
if [ -z "$CSV" ]; then
  CSV="$REPO_ROOT/Artifacts/swan-compare.csv"
  git -C "$REPO_ROOT" show origin/w3-swan-bake:docs/water-3/swan-compare.csv > "$CSV"
fi
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/WaveCheck/main.cpp" -lz -o "$OUT"
cd "$REPO_ROOT" && "$OUT" "$CSV"
