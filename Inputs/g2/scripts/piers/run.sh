#!/bin/sh
# Galveston piers pack: rebuild everything from the G2 tiles (dem, dsm, cover, ortho) with numpy + Pillow only.
# Usage: sh run.sh [Region] [processes]      Region defaults to GalvestonBay; GalvestonGulf once its tiles exist.
# Env: G2_OUT = the sailing-sim-g2 folder (default: two levels up from here), PIERS_WORK = scratch (default /tmp/g2piers).
set -e
cd "$(dirname "$0")"
REG=${1:-GalvestonBay}; NP=${2:-4}
python3 -I stage1.py "$REG" "$NP"     # candidate pixels per tile (about 10 min for 812 tiles on 4 cores)
python3 -I stage2.py "$REG"           # join, split boats from docks, classify, GeoJSON (about 1 min)
python3 -I seawall.py "$REG"          # Seawall step edge
python3 -I trace.py "$REG"            # jetties and Texas City Dike end to end; landmarks.geojson
