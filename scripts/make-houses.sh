#!/usr/bin/env bash
# Graphics G6: the shore's houses from the G2 footprints. Bakes Content/TerrainData/<World>.houses from
# Data/<World>/raw/g2/buildings.geojson.gz (git show origin/inputs:Inputs/g2/<World>/buildings.geojson.gz), then the Nanite
# tiles (scripts/bake_houses.py). Run scripts/build.sh and scripts/make-content.sh (M_HouseKitWall, M_HouseKitRoof) first.
source "$(dirname "$0")/env.sh"
set -euo pipefail
for W in RayHubbard GalvestonBay; do
	if [[ -f "$REPO_ROOT/Data/$W/raw/g2/buildings.geojson.gz" ]]; then
		"$REPO_ROOT/Tools/venv/bin/python" -I "$REPO_ROOT/Tools/terrain/build_houses.py" "$W"
	fi
done
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/bake_houses.py" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/bake-houses.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/bake-houses.log"; exit 1; }
grep -E "Baked the|Removed stale|Error" "$ARTIFACTS/bake-houses.log" | grep -v "^.*LogSailing: Display: Baked" || true
