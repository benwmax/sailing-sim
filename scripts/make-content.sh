#!/usr/bin/env bash
# Regenerates the content built from scripts: materials (make_materials.py), then the Lake map (make_lake_map.py).
# Run after scripts/build.sh.
source "$(dirname "$0")/env.sh"
"$REPO_ROOT/Tools/venv/bin/python" -I "$REPO_ROOT/scripts/make_sail_marks.py" > /dev/null
mkdir -p "$ARTIFACTS/models/world" && "$REPO_ROOT/Tools/venv/bin/python" -I "$REPO_ROOT/Tools/blender/make_leaf_atlas.py" "$ARTIFACTS/models/world/T_LeafAtlas.png"
# Graphics G1: the cloud noise volumes (Tools/clouds/make_cloud_noise.py), baked once; CLOUD_NOISE=1 rebakes them.
if [[ -n "${CLOUD_NOISE:-}" || ! -f "$REPO_ROOT/Content/Materials/Clouds/T_CloudShape.uasset" ]]; then
	"$REPO_ROOT/Tools/venv/bin/python" -I "$REPO_ROOT/Tools/clouds/make_cloud_noise.py" "$ARTIFACTS/clouds" > /dev/null
	"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/import_cloud_noise.py" \
		-unattended -nosplash -nosound -NoP4 -stdout > "$ARTIFACTS/import_cloud_noise.log" 2>&1
fi
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
