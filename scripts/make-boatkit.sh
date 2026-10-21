#!/usr/bin/env bash
# Boat kit (docs/boatkit-1): builds the shared fittings kit, dresses each boat from its layout and character sheet and,
# with --render, renders the review views. Needs Blender (brew install --cask blender; on the PC, blender.exe on PATH)
# or the bpy Python module (pip install bpy). Boat fidelity 2 (docs/boat-fidelity-2): it first bakes the kit's trim sheet
# (Tools/boatkit/make_trim_sheet.py, Inputs/boat-kit), exports a hero and a light FBX per part to Artifacts/boatkit/kit, and
# with --render lays out the review sheets (make_review_sheet.py); scripts/import_hardware_kit.py then imports the kit into
# /Game/Boats/Kit (run it in the editor; the PC's scripts\windows\make-boatkit.ps1 -Import does both).
# Usage: scripts/make-boatkit.sh [--render] [character ...]   (characters default to all in Tools/boatkit/characters)
# Photo match: Tools/boatkit/photomatch/solve_camera.py <matches.json> <sockets> <landmarks>, then
#   dress_boat.py ... --render --camera <photo>.camera.json --photo <photo.jpg> (photos stay out of the repo).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$REPO_ROOT/Artifacts/boatkit"
KIT="$REPO_ROOT/Tools/boatkit"
mkdir -p "$OUT"
RENDER=""
CHARS=()
for a in "$@"; do
	if [[ "$a" == "--render" ]]; then RENDER="--render"; else CHARS+=("$a"); fi
done
[[ ${#CHARS[@]} -eq 0 ]] && for f in "$KIT"/characters/*.json; do CHARS+=("$(basename "$f" .json)"); done
run() {   # run a Tools/boatkit script with Blender, or with the bpy module when no Blender is installed
	local script="$1"; shift
	local blender="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
	if [[ -x "$blender" ]]; then
		"$blender" -b --factory-startup -noaudio -P "$script" -- "$@"
	else
		python3 "$script" "$@"
	fi
}
python3 "$KIT/make_trim_sheet.py"
run "$KIT/build_kit.py" "$OUT/kit" $RENDER > "$OUT/kit.log" 2>&1 || { tail -30 "$OUT/kit.log"; exit 1; }
grep -E "^Kit: [0-9]+ parts" "$OUT/kit.log"
[[ -n "$RENDER" ]] && python3 "$KIT/make_review_sheet.py" "$OUT/kit"
for C in "${CHARS[@]}"; do
	BOAT=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['class'].lower())" "$KIT/characters/$C.json")
	run "$KIT/dress_boat.py" "$KIT/layouts/$BOAT.json" "$KIT/characters/$C.json" "$OUT/$C" $RENDER > "$OUT/$C.log" 2>&1 \
		|| { tail -30 "$OUT/$C.log"; exit 1; }
	grep -E "^Dress: [0-9]+ kit parts|^Layout:" "$OUT/$C.log" || true
done
