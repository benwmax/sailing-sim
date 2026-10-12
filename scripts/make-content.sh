#!/usr/bin/env bash
# Regenerates the content built from scripts: materials (make_materials.py), then the Lake map (make_lake_map.py).
# Run after scripts/build.sh.
source "$(dirname "$0")/env.sh"
for SCRIPT in make_materials.py make_lake_map.py; do
	# The map is rebuilt from scratch; remove the old file so stale actor classes can't block it.
	[[ "$SCRIPT" == make_lake_map.py ]] && rm -f "$REPO_ROOT/Content/Maps/Lake.umap"
	"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/$SCRIPT" \
		-unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/${SCRIPT%.py}.log" 2>&1
	if grep -qE "Traceback|Error: .*(Python|compil)" "$ARTIFACTS/${SCRIPT%.py}.log"; then
		grep -E -A8 "Traceback|Error: " "$ARTIFACTS/${SCRIPT%.py}.log" | head -40 >&2
		exit 1
	fi
	grep -E "Materials built|Lake map saved" "$ARTIFACTS/${SCRIPT%.py}.log" || true
done
test -f "$REPO_ROOT/Content/Maps/Lake.umap"
