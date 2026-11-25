#!/usr/bin/env bash
# Wildlife Phase 1 (docs/wildlife-1/README.md): the mid-distance bird bodies in Blender headless
# (Tools/blender/build_birds.py -> Artifacts/models/birds/SM_Bird_<Style>.fbx), then the editor builds M_BirdFar and
# M_BirdMid and imports the bodies into /Game/Wildlife/Birds (scripts/import_birds.py). Run after scripts/build.sh and
# scripts/make-content.sh. Usage: [BLENDER=<blender or a python with bpy>] scripts/make-birds.sh [--no-import]
source "$(dirname "$0")/env.sh"
set -euo pipefail
OUT="$ARTIFACTS/models/birds"
mkdir -p "$OUT"
# Blender, or BLENDER=<a python with the bpy module> (as scripts/make-c22-hero.sh).
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
if [[ "$BLENDER" == *python* ]]; then BLEND_RUN=("$BLENDER" "$REPO_ROOT/Tools/blender/build_birds.py" "$OUT")
else BLEND_RUN=("$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/build_birds.py" -- "$OUT"); fi
"${BLEND_RUN[@]}" > "$ARTIFACTS/blender-build_birds.log" 2>&1 || { tail -30 "$ARTIFACTS/blender-build_birds.log"; exit 1; }
grep -E "^Birds: " "$ARTIFACTS/blender-build_birds.log"
[[ "${1:-}" == "--no-import" ]] && exit 0
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_birds.py $OUT" \
	-unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/import_birds.log" 2>&1 || true
if grep -qE "Traceback|Error: .*(Python|compil)" "$ARTIFACTS/import_birds.log"; then
	grep -E -A8 "Traceback|Error: " "$ARTIFACTS/import_birds.log" | head -40 >&2
	exit 1
fi
grep -E "Birds: " "$ARTIFACTS/import_birds.log" || true
grep -q "Birds: done" "$ARTIFACTS/import_birds.log" || { echo "import_birds.py did not finish; see $ARTIFACTS/import_birds.log" >&2; exit 1; }
