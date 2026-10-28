#!/usr/bin/env bash
# docs/long-wave-fft/: builds SailingPhysics standalone with clang (no Unreal) and runs the long-wave FFT's checks (the same
# as SailingSim.Physics.LongWaves.*), then times the FFT kernel and a key's grids on this machine.
# Usage: scripts/long-wave-check.sh [--swan]  (--swan also runs SeaMapSwan: the sea map with a channel per cascade against
# SWAN's ten points, from origin/w3-swan-bake's docs/water-3/points.csv)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/long-wave-check"
mkdir -p "$REPO_ROOT/Artifacts"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/LongWaveCheck/main.cpp" -lz -o "$OUT"
cd "$REPO_ROOT"
if [ "${1:-}" = "--swan" ]; then
  POINTS="$REPO_ROOT/Artifacts/swan-points.csv"
  git -C "$REPO_ROOT" show origin/w3-swan-bake:docs/water-3/points.csv > "$POINTS"
  "$OUT" --swan "$POINTS"
else
  "$OUT"
fi
