#!/usr/bin/env bash
# Catalina 22 rebuild, game wiring (docs/c22-12): builds the rebuild's model (Tools/shipkit/catalina22/build_c22.py, about
# 2 min), cuts it into the game's parts (export_game_c22.py -> Artifacts/models/SM_C22Hero_*.fbx and C22Hero_sockets.json,
# as game_c22.json says) and imports them to /Game/Boats/C22Hero (scripts/import_boats.py c22hero). Then the player's
# Catalina 22 is the rebuilt boat (ASailboatPawn::ModelMeshesFor; -SailingClassicC22 compares with the fleet model, which
# AI boats keep) and SailingSim.Visual.C22HeroMesh holds her to the physics. Run scripts/make-content.sh first (the boat
# library). Needs Blender (brew install --cask blender) or BLENDER=<a python with the bpy module>.
# Usage: scripts/make-c22-hero.sh [--no-import]     C22_REBUILD=1 rebuilds the .blend even when it is newer than its sources.
source "$(dirname "$0")/env.sh"
set -euo pipefail
MODELS="$ARTIFACTS/models"
BUILD="$ARTIFACTS/c22-build"
SRC="$REPO_ROOT/Tools/shipkit/catalina22"
mkdir -p "$MODELS" "$BUILD"
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
run_blender() {   # (a Blender binary takes -b -P <script> --; a python with bpy takes the script and its args)
	if [[ "$BLENDER" == *python* ]]; then "$BLENDER" "$1" "${@:2}"; else "$BLENDER" -b --factory-startup -noaudio -P "$1" -- "${@:2}"; fi
}
# The build is made again only when a source in Tools/shipkit/catalina22 is newer than it (the export's own files aside).
if [[ -n "${C22_REBUILD:-}" || ! -f "$BUILD/c22.blend" ]] \
	|| [[ -n "$(find "$SRC" -maxdepth 1 \( -name '*.py' -o -name '*.json' \) ! -name export_game_c22.py ! -name game_c22.json -newer "$BUILD/c22.blend" | head -1)" ]]; then
	run_blender "$SRC/build_c22.py" "$BUILD" > "$ARTIFACTS/blender-c22.log" 2>&1 || { tail -30 "$ARTIFACTS/blender-c22.log"; exit 1; }
	grep -E "^C22:" "$ARTIFACTS/blender-c22.log" || true
fi
run_blender "$SRC/export_game_c22.py" "$BUILD" "$MODELS" > "$ARTIFACTS/blender-c22hero.log" 2>&1 || { tail -30 "$ARTIFACTS/blender-c22hero.log"; exit 1; }
grep -E "^C22Hero:" "$ARTIFACTS/blender-c22hero.log" || true
[[ "${1:-}" == "--no-import" ]] && exit 0
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_boats.py c22hero" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/import-c22hero.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/import-c22hero.log"; exit 1; }
grep -E "LogPython: (Imported|Error|Warning)" "$ARTIFACTS/import-c22hero.log" || true
