#!/usr/bin/env bash
# W1: a top-down map of the wind field (docs/w1/puff-map.png): builds Tools/wind/DumpField.cpp standalone and plots it.
# Usage: Tools/wind/plot_field.sh [month] [hour] [knots]
set -euo pipefail
cd "$(dirname "$0")/../.."
SRC=Source/SailingPhysics
mkdir -p Artifacts
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp) Tools/wind/DumpField.cpp -o Artifacts/dump-field
Artifacts/dump-field "${1:-7}" "${2:-15}" "${3:-12}" > Artifacts/wind-field.txt
Tools/venv/bin/python -I Tools/wind/plot_field.py Artifacts/wind-field.txt docs/w1/puff-map.png
