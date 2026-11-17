#!/usr/bin/env bash
# Cannon fire's effects (docs/cannon-fire/): the smoke and flame textures (Tools/shipkit/frigate/make_cannon_textures.py,
# into Artifacts/cannon-fx), then their import and the materials M_CannonSmoke and M_CannonFlash (scripts/import_cannon_fx.py).
# Run after scripts/build.sh and make-content.sh. CANNON_FX_ONLY=textures,smoke,flash limits the editor half.
source "$(dirname "$0")/env.sh"
"$REPO_ROOT/Tools/venv/bin/python" -I "$REPO_ROOT/Tools/shipkit/frigate/make_cannon_textures.py" "$ARTIFACTS/cannon-fx" --preview
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_cannon_fx.py $ARTIFACTS/cannon-fx" \
	-unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/import_cannon_fx.log" 2>&1
if grep -qE "Traceback|Error: .*(Python|compil)" "$ARTIFACTS/import_cannon_fx.log"; then
	grep -E -A8 "Traceback|Error: " "$ARTIFACTS/import_cannon_fx.log" | head -40 >&2
	exit 1
fi
grep -E "Cannon fx:" "$ARTIFACTS/import_cannon_fx.log" || { echo "import_cannon_fx.py did not finish; see $ARTIFACTS/import_cannon_fx.log" >&2; exit 1; }
