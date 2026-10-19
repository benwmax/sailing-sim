#!/usr/bin/env bash
# Wide World Rendering PR 1 (docs/world-far): the far coast ring. Fetches the Copernicus GLO-90 tiles when missing
# (Tools/terrain/fetch_far_dem.sh), bakes <World>.far (Tools/terrain/build_far_ring.py) and builds its Nanite tiles in
# /Game/World/Far (scripts/bake_far_ring.py, UWorldKitLibrary::BakeFarRing). Run scripts/build.sh and scripts/make-content.sh
# (M_FarLand) first. Usage: scripts/make-far-ring.sh [World ...]   (default GalvestonBay GulfPassage Marseille)
source "$(dirname "$0")/env.sh"
set -euo pipefail
WORLDS=("$@")
[[ ${#WORLDS[@]} -gt 0 ]] || WORLDS=(GalvestonBay GulfPassage Marseille)
START=$(date +%s)
"$REPO_ROOT/Tools/terrain/fetch_far_dem.sh" "${WORLDS[@]}"
"$REPO_ROOT/Tools/venv/bin/python" -I "$REPO_ROOT/Tools/terrain/build_far_ring.py" "${WORLDS[@]}"
"$EDITOR_CMD" "$PROJECT" -run=pythonscript -script="$REPO_ROOT/scripts/bake_far_ring.py ${WORLDS[*]}" -unattended -nosplash -nosound -NoP4 -stdout -FullStdOutLogOutput > "$ARTIFACTS/bake-far-ring.log" 2>&1 \
	|| { tail -30 "$ARTIFACTS/bake-far-ring.log"; exit 1; }
grep -E "Far ring|Removed stale|Error" "$ARTIFACTS/bake-far-ring.log" | grep -v "LogSailing: Display" | sed 's/.*LogPython: //' || true
echo "Far ring baked in $(( $(date +%s) - START )) s; $(du -sh "$REPO_ROOT/Content/World/Far" | cut -f1) in Content/World/Far"
