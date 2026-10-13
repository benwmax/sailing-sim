#!/usr/bin/env bash
# Visual V6: regenerates the world models (trees, and later the structure kits) in Blender headless
# (Tools/blender/build_*.py -> Artifacts/models/world/*.fbx) and imports them into /Game/World (scripts/import_world.py).
# Run scripts/make-content.sh first (the materials and the leaf atlas). Usage: scripts/make-world-models.sh [--no-import]
source "$(dirname "$0")/env.sh"
set -euo pipefail
OUT="$ARTIFACTS/models/world"
mkdir -p "$OUT"
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
for GEN in build_trees build_props build_navaids; do
	"$BLENDER" -b --factory-startup -noaudio -P "$REPO_ROOT/Tools/blender/$GEN.py" -- "$OUT" > "$ARTIFACTS/blender-$GEN.log" 2>&1 \
		|| { tail -30 "$ARTIFACTS/blender-$GEN.log"; exit 1; }
	grep -E "^[A-Z][a-z]+: " "$ARTIFACTS/blender-$GEN.log" | head -40 || true
done
[[ "${1:-}" == "--no-import" ]] && exit 0
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_world.py" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/import-world.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/import-world.log"; exit 1; }
grep -E "LogPython: (Imported|Error|Warning)" "$ARTIFACTS/import-world.log" || true
