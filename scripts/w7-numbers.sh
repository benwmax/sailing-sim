#!/usr/bin/env bash
# W7 numbers (docs/water-7/numbers.md): the wind's puffs against the stations. Builds Tools/wind/PuffShape.cpp with the
# SailingPhysics sources standalone (no Unreal), samples the lake's weather wind at 12 kn for each season's afternoon,
# and analyses both sides with Tools/wind/puff_shape.py (puff duration, veer at the peak, strength).
# Usage: scripts/w7-numbers.sh [hours per run]   Needs Data/Wind/raw/asos (Tools/wind/fetch_wind.sh) for the stations.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/Source/SailingPhysics"
OUT="$REPO_ROOT/Artifacts/w7"
HOURS="${1:-6}"
mkdir -p "$OUT"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/wind/PuffShape.cpp" -o "$OUT/puff-shape"
cd "$REPO_ROOT"
SERIES=()
for CASE in "1 9" "4 12" "7 15" "10 15"; do
	read -r MONTH HOUR <<< "$CASE"
	"$OUT/puff-shape" "$MONTH" "$HOUR" "$HOURS" 6 > "$OUT/puffs-$MONTH-$HOUR.txt" &
	SERIES+=("$OUT/puffs-$MONTH-$HOUR.txt")
done
wait
PY="$REPO_ROOT/Tools/venv/bin/python"
"$PY" -I "$REPO_ROOT/Tools/wind/puff_shape.py"
"$PY" -I "$REPO_ROOT/Tools/wind/puff_shape.py" --series "${SERIES[@]}"
