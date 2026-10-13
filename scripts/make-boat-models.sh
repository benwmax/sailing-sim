#!/usr/bin/env bash
# Visual V2: regenerates the boat models. Exports the physics geometry (Tools/BoatExport, standalone C++), builds the
# model in Blender headless (Tools/blender/build_<boat>.py -> Artifacts/models/*.fbx), then imports it into
# /Game/Boats/<Boat> with Nanite and the generated materials (scripts/import_boats.py). Run scripts/make-content.sh
# first (the materials). Needs Blender (brew install --cask blender).
# Usage: scripts/make-boat-models.sh [--no-import]
source "$(dirname "$0")/env.sh"
set -euo pipefail
SRC="$REPO_ROOT/Source/SailingPhysics"
MODELS="$ARTIFACTS/models"
mkdir -p "$MODELS"
SOURCES=$(ls "$SRC"/Private/*.cpp | grep -v SailingPhysicsModule.cpp)
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -Wshadow -I"$SRC/Public" $SOURCES "$REPO_ROOT/Tools/BoatExport/main.cpp" -o "$ARTIFACTS/boat-export"
"$ARTIFACTS/boat-export" j22 "$MODELS/j22.json"
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_j22.py" -- "$MODELS/j22.json" "$MODELS" > "$ARTIFACTS/blender-j22.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/blender-j22.log"; exit 1; }
grep -E "^J22:" "$ARTIFACTS/blender-j22.log" || true
"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_crew.py" -- "$MODELS" > "$ARTIFACTS/blender-crew.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/blender-crew.log"; exit 1; }
grep -E "^Crew:" "$ARTIFACTS/blender-crew.log" || true
# Visual V7: the MetaHuman crew's life jacket and cap (Tools/blender/build_crew_gear.py).
"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_crew_gear.py" -- "$MODELS" > "$ARTIFACTS/blender-gear.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/blender-gear.log"; exit 1; }
grep -E "^Gear:" "$ARTIFACTS/blender-gear.log" || true
# Visual V7: the other seven boats from the same exported physics (Tools/blender/build_fleet.py).
for PAIR in sunfish:Sunfish ilca7:ILCA7 catalina22:Catalina22 catalina30:Catalina30 hobie16:Hobie16 corsair880:Corsair880 lagoon42:Lagoon42; do
	KEY="${PAIR%%:*}"; TAG="${PAIR#*:}"
	"$ARTIFACTS/boat-export" "$KEY" "$MODELS/$KEY.json"
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_fleet.py" -- "$MODELS/$KEY.json" "$TAG" "$MODELS" > "$ARTIFACTS/blender-$TAG.log" 2>&1 \
		|| { tail -30 "$ARTIFACTS/blender-$TAG.log"; exit 1; }
	grep -E "^$TAG: LOA" "$ARTIFACTS/blender-$TAG.log" || true
done
# The keelboats as they lie in their slips (the marina's neighbours).
for PAIR in J22:j22 Catalina22:catalina22 Catalina30:catalina30; do
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_berthed.py" -- "${PAIR%%:*}" "$MODELS/${PAIR#*:}.json" "$MODELS" 2>&1 | grep -E "^Berthed:" || true
done
[[ "${1:-}" == "--no-import" ]] && exit 0
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_boats.py ${IMPORT_ARGS:-}" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/import-boats.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/import-boats.log"; exit 1; }
grep -E "LogPython: (Imported|Error|Warning)" "$ARTIFACTS/import-boats.log" || true
