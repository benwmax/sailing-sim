#!/usr/bin/env bash
# Wide World Rendering, PR 1 (the far coast ring, docs/world-far): downloads the Copernicus DEM GLO-90 tiles that
# Tools/terrain/build_far_ring.py bakes into the far coast band, into Data/Far/raw (git-ignored). The tiles are the
# 1-degree cells of the world's box widened by its ring (Tools/terrain/far_ring.json). Source: copernicus-dem-90m on AWS
# Open Data; (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the
# European Union and ESA; free licence with attribution (Inputs/licences, CREDITS.md). A missing tile is all sea.
# ULTRA=1 fetches the GLO-30 tiles instead (copernicus-dem-30m, glo30_<tile>.tif) for build_far_ring.py --ultra.
# Run: [ULTRA=1] Tools/terrain/fetch_far_dem.sh [World ...]   (default GalvestonBay GulfPassage Marseille)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="$ROOT/Data/Far/raw"
mkdir -p "$RAW"
WORLDS=("$@")
[[ ${#WORLDS[@]} -gt 0 ]] || WORLDS=(GalvestonBay GulfPassage Marseille)
for T in $("$ROOT/Tools/venv/bin/python" -I "$ROOT/Tools/terrain/build_far_ring.py" --tiles "${WORLDS[@]}"); do
	RES=90; COG=30; [[ "${ULTRA:-}" == 1 ]] && RES=30 && COG=10
	OUT="$RAW/glo${RES}_$T.tif"
	[[ -s "$OUT" ]] && continue
	ls "$ROOT"/Data/*/raw/far/glo${RES}_$T.tif >/dev/null 2>&1 && continue   # a world's own copy (Tools/coast/fetch_world.py)
	STEM="Copernicus_DSM_COG_${COG}_${T}_DEM"
	if curl -sSf -m 300 -o "$OUT.part" "https://copernicus-dem-${RES}m.s3.amazonaws.com/$STEM/$STEM.tif"; then
		mv "$OUT.part" "$OUT"; echo "  $T"
	else
		rm -f "$OUT.part"; echo "  $T: no tile (all sea)"
	fi
done
echo "GLO tiles in $RAW"
